import requests
import logging
import datetime
from mcp_project.xero_config import XERO_ITEMS_URL

class MCPXeroSyncItemService:

    def __init__(self, odoo_client):
        self.service_name = "Odoo → Xero Item Sync MCP Server"
        self.odoo_client = odoo_client

    def get_tools_schema(self):
        return [
            {
                "name": "sync_all_items",
                "description": "Sync all active items (products) from Odoo into Xero.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "access_token": {"type": "string", "description": "Fresh Xero OAuth2 access token"},
                        "tenant_id": {"type": "string", "description": "Xero tenant ID"}
                    },
                    "required": ["access_token", "tenant_id"]
                }
            }
        ]

    def _post_to_xero(self, payload, access_token, tenant_id):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        try:
            print(">>> _post_to_xero PRE_SYNC payload:", payload)
            response = requests.post(XERO_ITEMS_URL, json=payload, headers=headers)
            print(">>> _post_to_xero SYNC status:", response.status_code)
            response.raise_for_status()
            print(">>> _post_to_xero POST_SYNC response:", response.json())
            return response.json()
        except Exception as e:
            print(">>> _post_to_xero POST_SYNC Exception:", e)
            if hasattr(e, 'response') and e.response is not None:
                print(">>> Xero error body:", e.response.text)
            logging.error(f"Xero API error: {str(e)}")
            return None

    def _build_xero_item_payload(self, item):
        code = (item.get("code") or "").strip()
        return {
            "Code": code,
            "Name": item["name"],
            "Description": item.get("description", ""),
            "IsTrackedAsInventory": True,
            "InventoryAssetAccountCode": "630",
            "SalesDetails": {
                "UnitPrice": item.get("sale_price", 0),
                "AccountCode": "200",
                "TaxType": "OUTPUT"
            },
            "PurchaseDetails": {
                "UnitPrice": item.get("purchase_price", 0),
                "COGSAccountCode": "310",
                "TaxType": "NONE"
            }
        }




    def sync_all_items(self, access_token, tenant_id):
        print(">>> sync_all_items PRE_SYNC fetching products...")
        items = self.odoo_client.get_products()

        # 1. Filter valid items
        valid_items = []
        for item in items:
            code = (item.get("code") or "").strip()
            if not code or not item.get("name"):
                print(f"Skipping item '{item.get('name')}' - Missing a valid SKU/Code.")
                continue

             
            if item.get("sync_status") in ("PENDING", "FAILED", None):
                print("----> DEBUG...10...item, sync_status", item, item.get("sync_status"))

                valid_items.append(item)
            #else:
            #    print(f"Skipping item '{item.get('name')}' - Status={item.get('sync_status')}")

        if not valid_items:
            print("No valid items to sync after filtering SKUs and statuses.")
            return []

        results = []
        for i in range(0, len(valid_items), 50):
            batch = valid_items[i:i+50]

            # 2. Mark batch as IN_PROGRESS
            for item in batch:
                self.odoo_client.models.execute_kw(
                    self.odoo_client.db, self.odoo_client.uid, self.odoo_client.odoo_pass,
                    'product.product', 'write',
                    [[item["id"]], {"sync_status": "IN_PROGRESS"}]
                )

            # 3. Build payload
            payload = {"Items": [self._build_xero_item_payload(item) for item in batch]}
            print(f">>> Sending Item batch {i//50+1}, size={len(batch)}")

            # 4. Push to Xero
            batch_result = self._post_to_xero(payload, access_token, tenant_id)

            # 5. Update sync_status based on response
            if batch_result and "Items" in batch_result:
                for idx, item in enumerate(batch):
                    xero_item = batch_result["Items"][idx]

                    item_id = xero_item.get("ItemID")
                    errors = xero_item.get("ValidationErrors", [])

                    print("----> DEBUG...100...item_id, errors", item_id, errors)

                    # 檢查 ValidationErrors
                    if errors and len(errors) > 0:
                        sync_status = "FAILED"
                        print(f"----> Item {item.get('code')} failed: {errors}")
                    else:
                        # ✅ 判斷成功：只要有 ItemID 並且冇錯，就算成功
                        sync_status = "SUCCESS" if item_id else "FAILED"

                    self.odoo_client.models.execute_kw(
                        self.odoo_client.db, self.odoo_client.uid, self.odoo_client.odoo_pass,
                        'product.product', 'write',
                        [[item["id"]], {
                            "sync_status": sync_status,
                            "acct_sync_id": item_id,
                            "acct_sync_datetime": datetime.datetime.now(),
                        }]
                    )

                # append once per batch
                results.append(batch_result)

        return results




