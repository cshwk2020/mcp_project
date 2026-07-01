import requests
import logging
from mcp_project.xero_config import XERO_INVOICES_URL
import datetime 

class MCPXeroSyncSalesOrderService:

    def __init__(self, odoo_client):
        self.service_name = "Odoo → Xero Sales Order Sync MCP Server"
        self.odoo_client = odoo_client

    def get_tools_schema(self):
        return [
            {
                "name": "sync_all_sales_orders",
                "description": "Sync all active sales orders from Odoo into Xero as standard Invoices (tracked inventory enabled).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "access_token": {"type": "string", "description": "Fresh Xero OAuth2 access token"},
                        "tenant_id": {"type": "string", "description": "Xero tenant ID"}
                    },
                    "required": ["access_token", "tenant_id"]
                }
            },
            {
                "name": "delete_all_preauth_sos",
                "description": "Delete all active Sales Orders (Quotes) in Xero (DRAFT, SENT, ACCEPTED).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "access_token": {"type": "string", "description": "Fresh Xero OAuth2 access token"},
                        "tenant_id": {"type": "string", "description": "Xero tenant ID"}
                    },
                    "required": ["access_token", "tenant_id"]
                }
            },
            {
                "name": "delete_all_postauth_sos",
                "description": "Void all Awaiting Payment Invoices (AUTHORISISED) in Xero.",
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
            print(">>> _post_to_xero PRE_SYNC SO payload:", payload)
            response = requests.post(XERO_INVOICES_URL, json=payload, headers=headers)
            print(">>> _post_to_xero SYNC SO status:", response.status_code)
            response.raise_for_status()
            print(">>> _post_to_xero POST_SYNC SO response:", response.json())
            return response.json()
        except Exception as e:
            print(">>> _post_to_xero POST_SYNC SO Exception:", e)
            if hasattr(e, 'response') and e.response is not None:
                print(">>> Xero SO error body:", e.response.text)
            logging.error(f"Xero API SO error: {str(e)}")
            return None

    def _build_xero_so_payload(self, so):
        # Fetch customer details from Odoo
        customer_info = self.odoo_client.get_vendor_contact(so.get("partner_id"))
        customer_ref = customer_info.get("ref", "")

        # parse 出 ContactID
        contact_id = None
        if customer_ref and customer_ref.startswith("XERO:"):
            contact_id = customer_ref.replace("XERO:", "")

        xero_line_items = []
        for item in so.get("line_items", []):
            xero_line_items.append({
                "ItemCode": item.get("item_code", ""),   # ✅ 必須傳 ItemCode → Xero tracked inventory
                "Description": item.get("description", ""),
                "Quantity": item.get("quantity", 0),
                "UnitAmount": item.get("unit_price", 0),
                "AccountCode": item.get("account_code", "200")  # Sales Revenue
            })

        return {
            "Type": "ACCREC",  # Accounts Receivable (Sales Invoice)
            "InvoiceNumber": so["so_number"],
            "Contact": {
                "ContactID": contact_id,  # ✅ 用 ContactID
                "EmailAddress": customer_info.get("email", ""),
            },
            "Date": so.get("date"),
            "DueDate": so.get("due_date") or so.get("date"),
            "Status": "AUTHORISED",
            "LineItems": xero_line_items,
            "Reference": f"ODOO-SO-{so.get('id')}"
        }

    def sync_sales_order(self, so, access_token, tenant_id):
        print(">>> sync_sales_order PRE_SYNC SO:", so)
        payload = self._build_xero_so_payload(so)
        result = self._post_to_xero(payload, access_token, tenant_id)
        print(">>> sync_sales_order POST_SYNC result:", result)
        return result



    def sync_all_sales_orders(self, access_token, tenant_id):

        print(">>> sync_all_sales_orders PRE_SYNC fetching SOs...")
        sos = self.odoo_client.get_sales_orders()

        # 1. Filter valid SOs
        valid_sos = []
        for so in sos:
            so_number = (so.get("so_number") or "").strip()
            customer_name = (so.get("customer_name") or "").strip()
            if not so_number or not customer_name:
                print(f"Skipping SO '{so_number}' - Missing SO Number or Customer Name.")
                continue

            # 只處理 PENDING / FAILED / None
            if so.get("sync_status") in ("PENDING", "FAILED", None):
                print("----> DEBUG...10...so, sync_status", so, so.get("sync_status"))
                valid_sos.append(so)
            else:
                print(f"Skipping SO '{so_number}' - Status={so.get('sync_status')}")

        if not valid_sos:
            print("No valid Sales Orders to sync after filtering.")
            return []

        results = []
        for i in range(0, len(valid_sos), 50):
            batch = valid_sos[i:i+50]

            # 2. Mark batch as IN_PROGRESS
            for so in batch:
                self.odoo_client.models.execute_kw(
                    self.odoo_client.db, self.odoo_client.uid, self.odoo_client.odoo_pass,
                    'sale.order', 'write',
                    [[so["id"]], {"sync_status": "IN_PROGRESS"}]
                )

            # 3. Build payload
            payload = {"Invoices": [self._build_xero_so_payload(so) for so in batch]}
            print(f">>> Sending SO batch {i//50+1}, size={len(batch)}")

            print('SO payload == ', payload)

            # 4. Push to Xero
            batch_result = self._post_to_xero(payload, access_token, tenant_id)

            # 5. Update sync_status based on response
            if batch_result and "Invoices" in batch_result:
                for idx, so in enumerate(batch):
                    inv = batch_result["Invoices"][idx]
                    invoice_id = inv.get("InvoiceID")
                    errors = inv.get("ValidationErrors", [])
                    status = inv.get("Status")

                    print("----> DEBUG...100...invoice_id, status, errors", invoice_id, status, errors)

                    # 判斷成功/失敗
                    if errors and len(errors) > 0:
                        sync_status = "FAILED"
                        print(f"----> SO {so.get('so_number')} failed: {errors}")
                    else:
                        sync_status = "SUCCESS" if (invoice_id and status == "AUTHORISED") else "FAILED"

                    self.odoo_client.models.execute_kw(
                        self.odoo_client.db, self.odoo_client.uid, self.odoo_client.odoo_pass,
                        'sale.order', 'write',
                        [[so["id"]], {
                            "sync_status": sync_status,
                            "acct_sync_id": invoice_id,
                            "acct_sync_datetime": datetime.datetime.now(),  # ✅ 統一用 Python datetime
                        }]
                    )

                results.append(batch_result)

        return results


    def delete_all_preauth_sos(self, access_token, tenant_id):
        """
        Delete all active Sales Orders (Quotes) and Awaiting Payment Invoices in Xero.
        Quotes endpoint handles DRAFT/SENT/ACCEPTED.
        Invoices endpoint handles AUTHORISED (Awaiting Payment).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        results = []

        # 1. Delete Quotes (Sales Orders)
        try:
            get_quotes_url = "https://api.xero.com/api.xro/2.0/Quotes?Statuses=DRAFT,SENT,ACCEPTED"
            get_resp = requests.get(get_quotes_url, headers=headers)
            get_resp.raise_for_status()
            quotes = get_resp.json().get("Quotes", [])
            if quotes:
                print(f"Found {len(quotes)} Quotes to delete...")
                so_updates = [{"QuoteID": q["QuoteID"], "Status": "DELETED"} for q in quotes]
                post_url = "https://api.xero.com/api.xro/2.0/Quotes"
                payload = {"Quotes": so_updates}
                post_resp = requests.post(post_url, json=payload, headers=headers)
                post_resp.raise_for_status()
                results.append({"deleted_quotes": post_resp.json().get("Quotes", [])})
            else:
                print("No active Quotes found.")
        except Exception as e:
            logging.error(f"Quote deletion failed: {str(e)}")

        return results



    def delete_all_postauth_sos(self, access_token, tenant_id):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        results = []

        try:
            get_invoices_url = "https://api.xero.com/api.xro/2.0/Invoices?Statuses=AUTHORISED"
            inv_resp = requests.get(get_invoices_url, headers=headers)
            inv_resp.raise_for_status()
            invoices = inv_resp.json().get("Invoices", [])
            if invoices:
                print(f"Found {len(invoices)} Invoices (Awaiting Payment) to void...")
                inv_updates = [{"InvoiceID": inv["InvoiceID"], "Status": "VOIDED"} for inv in invoices]
                post_url = "https://api.xero.com/api.xro/2.0/Invoices"
                payload = {"Invoices": inv_updates}
                post_resp = requests.post(post_url, json=payload, headers=headers)
                post_resp.raise_for_status()
                # 🔑 Return raw list, not wrapped dict
                results = post_resp.json().get("Invoices", [])
            else:
                print("No Awaiting Payment Invoices found.")
        except Exception as e:
            logging.error(f"Invoice deletion failed: {str(e)}")

        return results
