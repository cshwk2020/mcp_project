import requests
import logging
import datetime
from mcp_project.xero_config import XERO_PURCHASE_ORDERS_URL

class MCPXeroSyncPurchaseOrderService:

    def __init__(self, odoo_client):
        self.service_name = "Odoo → Xero Purchase Order Sync MCP Server"
        self.odoo_client = odoo_client

    def get_tools_schema(self):
        return [
            {
                "name": "sync_all_purchase_orders",
                "description": "Sync all active purchase orders from Odoo into Xero, and if received, update related vendor bill status.",
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
                "name": "delete_all_bills",
                "description": "Clear out and void all Accounts Payable bills in Xero to reset the environment.",
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
            response = requests.post(XERO_PURCHASE_ORDERS_URL, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"Xero API PO error body: {e.response.text}")
            logging.error(f"Xero API PO error: {str(e)}")
            return None

    def _build_xero_po_payload(self, po):
        vendor_info = self.odoo_client.get_vendor_contact(po.get("partner_id"))
        vendor_ref = vendor_info.get("ref", "") if vendor_info else ""
        contact_id = vendor_ref.replace("XERO:", "") if vendor_ref.startswith("XERO:") else None

        xero_line_items = [{
            "ItemCode": item.get("item_code", ""),
            "Description": item.get("description", ""),
            "Quantity": item.get("quantity", 0),
            "UnitAmount": item.get("unit_price", 0)
        } for item in po.get("line_items", [])]

        payload = {
            "PurchaseOrderNumber": po["po_number"],
            "Contact": {"ContactID": contact_id} if contact_id else {"Name": vendor_info.get("name")},
            "Date": po.get("date"),
            "Status": "AUTHORISED",
            "LineItems": xero_line_items,
            "Reference": f"{po.get('id')}00000{po.get('picking_id', 0)}"
        }
        return payload



    def sync_all_purchase_orders(self, access_token, tenant_id):

        print(">>> sync_all_purchase_orders PRE_SYNC fetching POs...")
        pos = self.odoo_client.get_purchase_orders()

        # 1. Filter valid POs
        valid_pos = []
        for po in pos:
            if not (po.get("po_number") or "").strip() or not (po.get("vendor_name") or "").strip():
                print(f"Skipping PO '{po.get('po_number')}' - Missing number/vendor.")
                continue

            # 只處理 PENDING / FAILED / None
            if po.get("sync_status") in ("PENDING", "FAILED", None):
                print("----> DEBUG...10...po, sync_status", po, po.get("sync_status"))
                valid_pos.append(po)
            else:
                print(f"Skipping PO '{po.get('po_number')}' - Status={po.get('sync_status')}")

        if not valid_pos:
            print("No valid Purchase Orders to sync after filtering.")
            return []

        results = []
        for i in range(0, len(valid_pos), 50):
            batch = valid_pos[i:i+50]

            # 2. Mark batch as IN_PROGRESS
            for po in batch:
                self.odoo_client.models.execute_kw(
                    self.odoo_client.db, self.odoo_client.uid, self.odoo_client.odoo_pass,
                    'purchase.order', 'write',
                    [[po["id"]], {"sync_status": "IN_PROGRESS"}]
                )

            # 3. Build payload
            payload = {"PurchaseOrders": [self._build_xero_po_payload(po) for po in batch]}
            print(f">>> Sending PO batch {i//50+1}, size={len(batch)}")

            # 4. Push to Xero
            batch_result = self._post_to_xero(payload, access_token, tenant_id)
            print("sync_all_purchase_orders...batch_result == ", batch_result)

            if batch_result and "PurchaseOrders" in batch_result:
                bill_pos = []

                for idx, po in enumerate(batch):
                    xero_po = batch_result["PurchaseOrders"][idx]
                    po_xero_id = xero_po.get("PurchaseOrderID")
                    errors = xero_po.get("ValidationErrors", [])
                    status = xero_po.get("Status")

                    print("----> DEBUG...100...po_id, status, errors", po_xero_id, status, errors)

                    # 判斷成功/失敗
                    if errors and len(errors) > 0:
                        sync_status = "FAILED"
                        print(f"----> PO {po.get('po_number')} failed: {errors}")
                    else:
                        sync_status = "SUCCESS" if (po_xero_id and status == "AUTHORISED") else "FAILED"

                    self.odoo_client.models.execute_kw(
                        self.odoo_client.db, self.odoo_client.uid, self.odoo_client.odoo_pass,
                        'purchase.order', 'write',
                        [[po["id"]], {
                            "sync_status": sync_status,
                            "acct_sync_id": po_xero_id,
                            "acct_sync_datetime": datetime.datetime.now(),
                        }]
                    )

                    po_id = po.get("id")
                    po_state = self.odoo_client.get_po_state(po_id) if po_id else {}
                    if po_state.get("received") or po_state.get("billed"):
                        bill_pos.append(xero_po)

                # 5. Only call bill update once, with all collected POs
                bill_update = None
                if bill_pos:
                    bill_update = self._update_po_bill_status({"PurchaseOrders": bill_pos}, access_token, tenant_id)

                results.append({
                    "PurchaseOrders": batch_result["PurchaseOrders"],
                    "bill_update": bill_update
                })

        return results




    def _update_po_bill_status(self, po_resp, access_token, tenant_id):
        print("_update_po_bill_status...BEFORE...po_resp == ", po_resp)
        xero_pos = po_resp["PurchaseOrders"]  # now handle list of POs

        invoices = []
        for xero_po in xero_pos:
            contact_id = xero_po["Contact"]["ContactID"]

            bill_line_items = []
            for po_item in xero_po.get("LineItems", []):
                print("_update_po_bill_status...PO LineItemID == ", po_item.get("LineItemID"))
                bill_line_items.append({
                    "ItemCode": po_item.get("ItemCode"),
                    "Description": po_item.get("Description"),
                    "Quantity": po_item.get("Quantity"),
                    "UnitAmount": po_item.get("UnitAmount"),
                    #"AccountCode": "800",
                    "TaxType": po_item.get("TaxType", "INPUT"),
                    "PurchaseOrderLineItemID": po_item.get("LineItemID")
                })

            invoices.append({
                "Type": "ACCPAY",
                "Contact": {"ContactID": contact_id},
                "Date": datetime.date.today().isoformat(),
                "DueDate": datetime.date.today().isoformat(),
                "LineItems": bill_line_items,
                "Status": "AUTHORISED",
                "Reference": xero_po.get("PurchaseOrderNumber"),
                "CurrencyCode": xero_po.get("CurrencyCode", "HKD")
            })

        invoice_payload = {"Invoices": invoices}

        # 1. Post all Vendor Bills (Invoices) in one call
        invoice_url = "https://api.xero.com/api.xro/2.0/Invoices"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        invoice_resp = requests.post(invoice_url, json=invoice_payload, headers=headers)
        print("_update_po_bill_status...AFTER INVOICE...resp == ", invoice_resp.json())
        invoice_resp.raise_for_status()

        # 2. Update each PO status to BILLED
        po_updates = []
        for xero_po in xero_pos:
            po_update_url = f"https://api.xero.com/api.xro/2.0/PurchaseOrders/{xero_po['PurchaseOrderID']}"
            po_payload = {"Status": "BILLED"}
            po_update_resp = requests.post(po_update_url, json=po_payload, headers=headers)
            print("_update_po_bill_status...AFTER PO STATUS UPDATE...resp == ", po_update_resp.json())
            po_update_resp.raise_for_status()
            po_updates.append(po_update_resp.json())

        return {
            "invoice": invoice_resp.json(),
            "purchase_order_updates": po_updates
        }




    def delete_all_bills(self, access_token, tenant_id):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Fetch Awaiting Payment (AUTHORISISED) bills only
        get_url = "https://api.xero.com/api.xro/2.0/Invoices?Statuses=AUTHORISED&Type=ACCPAY"
        resp = requests.get(get_url, headers=headers)
        resp.raise_for_status()
        bills = resp.json().get("Invoices", [])

        if not bills:
            print("No Awaiting Payment bills to clear.")
            return []

        cleared = []
        for bill in bills:
            bill_id = bill["InvoiceID"]
            try:
                payload = {"Invoices": [{"InvoiceID": bill_id, "Status": "VOIDED"}]}
                resp = requests.post("https://api.xero.com/api.xro/2.0/Invoices", json=payload, headers=headers)
                resp.raise_for_status()
                print(f"Voided parent bill: {bill_id}")
                cleared.extend(resp.json().get("Invoices", []))
            except Exception as e:
                body = e.response.text if hasattr(e, 'response') and e.response else str(e)
                print(f"Skipping parent bill {bill_id} — error: {body}")
                continue

        print(f"Cleanup done. Processed {len(cleared)}/{len(bills)} parent bills.")
        return cleared




    def delete_all_pos(self, access_token, tenant_id):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Only fetch statuses that can actually be deleted/cancelled
        # DELETED POs must be excluded — Xero still returns them in some queries
        get_url = "https://api.xero.com/api.xro/2.0/PurchaseOrders?Statuses=DRAFT,AUTHORISED,BILLED,SUBMITTED"
        get_resp = requests.get(get_url, headers=headers)
        get_resp.raise_for_status()

        pos = get_resp.json().get("PurchaseOrders", [])

        # Double-filter: exclude anything already DELETED or VOIDED
        active_pos = [po for po in pos if po.get("Status") not in ("DELETED", "VOIDED")]

        if not active_pos:
            print("No active POs to delete.")
            return []

        print(f"Found {len(active_pos)} POs to delete.")
        deleted = []

        for po in active_pos:
            po_id = po["PurchaseOrderID"]
            po_number = po.get("PurchaseOrderNumber", po_id)
            status = po["Status"]

            try:
                # DRAFT → can be hard DELETED
                # AUTHORISED/BILLED/SUBMITTED → must be CANCELLED first, then DELETED
                if status == "DRAFT":
                    target_status = "DELETED"
                else:
                    target_status = "DELETED"  # Xero allows direct DELETED from AUTHORISED for POs

                payload = {"PurchaseOrders": [{"PurchaseOrderID": po_id, "Status": target_status}]}
                resp = requests.post(
                    "https://api.xero.com/api.xro/2.0/PurchaseOrders",
                    json=payload, headers=headers
                )

                if resp.status_code == 400:
                    body = resp.json()
                    elements = (body.get("Elements") or [{}])
                    returned_status = elements[0].get("Status", "")
                    msgs = [e.get("Message", "") for e in elements[0].get("ValidationErrors", [])]

                    if returned_status == "DELETED" or any("cannot be updated" in m or "already" in m.lower() for m in msgs):
                        print(f"PO {po_number} already deleted — skipping.")
                        deleted.append(po)
                        continue

                    # AUTHORISED POs sometimes need CANCELLED first
                    if any("cannot be deleted" in m.lower() for m in msgs):
                        cancel_payload = {"PurchaseOrders": [{"PurchaseOrderID": po_id, "Status": "CANCELLED"}]}
                        cancel_resp = requests.post(
                            "https://api.xero.com/api.xro/2.0/PurchaseOrders",
                            json=cancel_payload, headers=headers
                        )
                        cancel_resp.raise_for_status()
                        print(f"Cancelled PO {po_number}, now deleting...")

                        del_payload = {"PurchaseOrders": [{"PurchaseOrderID": po_id, "Status": "DELETED"}]}
                        del_resp = requests.post(
                            "https://api.xero.com/api.xro/2.0/PurchaseOrders",
                            json=del_payload, headers=headers
                        )
                        del_resp.raise_for_status()
                        deleted.extend(del_resp.json().get("PurchaseOrders", []))
                        print(f"Deleted PO {po_number} after cancel.")
                        continue

                    resp.raise_for_status()  # unknown 400 — surface it

                else:
                    resp.raise_for_status()
                    deleted.extend(resp.json().get("PurchaseOrders", []))
                    print(f"Deleted PO {po_number} (was {status}).")

            except Exception as e:
                body = e.response.text if hasattr(e, 'response') and e.response else str(e)
                print(f"Skipping PO {po_number} ({status}) — error: {body}")
                continue  # never block remaining POs

        print(f"PO cleanup done. Processed {len(deleted)}/{len(active_pos)}.")
        return deleted
        