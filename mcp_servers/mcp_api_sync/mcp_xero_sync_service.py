# -*- coding: utf-8 -*-
import xmlrpc.client
import json
import datetime
import time
import requests
import logging
from mcp_project.mcp_shared.vault_util import VaultUtil
from mcp_project.config import ODOO_BASE_URL, ODOO_DB
from mcp_project.xero_config import (
    load_xero_tokens, refresh_tokens, get_access_token,
    connectionAPI, xero_tenant_id, xero_tokens, 
    XERO_INVOICE_URL, XERO_MANUAL_JOURNAL_URL,
    XERO_AccountCode_COGS, XERO_AccountCode_Inventory
)
 

logger = logging.getLogger(__name__)

class MCPXeroSyncService:

    def __init__(self):
        self.service_name = "Odoo → Xero Sync MCP Server"
        _vault = VaultUtil()
        self.odoo_user = _vault.get_odoo_user()
        self.odoo_pass = _vault.get_odoo_pass()
        self.uid, self.models = self._get_models(self.odoo_user, self.odoo_pass)

    def _get_models(self, odoo_user, odoo_pass):
        common = xmlrpc.client.ServerProxy(f"{ODOO_BASE_URL}/xmlrpc/2/common")
        uid = common.authenticate(ODOO_DB, odoo_user, odoo_pass, {})
        if not uid:
            raise PermissionError("Failed authentication against Odoo.")
        models = xmlrpc.client.ServerProxy(f"{ODOO_BASE_URL}/xmlrpc/2/object")
        return uid, models

    def get_tools_schema(self):
        return [
            {
                "name": "pull_sale_orders_to_xero",
                "description": "Pull outstanding sale orders from Odoo and prepare JSON for Xero Invoice API.",
                "input_schema": {"type": "object", "properties": {}, "required": []}
            },
            {
                "name": "pull_stock_pickings_to_xero",
                "description": "Pull outstanding stock pickings from Odoo and prepare JSON for Xero Journal API.",
                "input_schema": {"type": "object", "properties": {}, "required": []}
            }
        ]

    
    def _generate_trans_group_id(self, saleorder_id, picking_id, cancel=False):
        import time
        ts = int(time.time_ns())
        if cancel:
            return f"{ts}_SO{saleorder_id}CANCEL_PK{picking_id}CANCEL"
        return f"{ts}_SO{saleorder_id}_PK{picking_id}"


    def _get_lineitems_from_sale_order(self, so):

        line_items = []
        
        for line_id in so["order_line"]:
            line = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "sale.order.line", "read", [line_id],
                {"fields": ["name","product_uom_qty","price_unit","product_id"]}
            )[0]
            product = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "product.product", "read", [[line["product_id"][0]]],
                {"fields": ["property_account_income_id"]}
            )[0]
            line_items.append({
                "Description": line["name"],
                "Quantity": line["product_uom_qty"],
                "UnitAmount": line["price_unit"],
                "AccountCode": product["property_account_income_id"][1] if product.get("property_account_income_id") else "200"
            })
        
        return line_items


        
    def _get_journalitems_from_pickling(self, pk):

        print("_get_journalitems_from_pickling...0...")
        print("_get_journalitems_from_pickling...10...pk==", pk)

        journal_lines = []
        for move_id in pk["move_ids"]:
            print("_get_journalitems_from_pickling...11...move_id==", move_id)
            move = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "stock.move", "read", [move_id],
                {"fields": ["product_id","product_uom_qty"]}
            )[0]
            print("_get_journalitems_from_pickling...12...move==", move)
            product = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "product.product", "read", [[move["product_id"][0]]],
                {"fields": ["name","standard_price","property_account_expense_id"]}
            )[0]
            print("_get_journalitems_from_pickling...13...product==", product)
            amount = move["product_uom_qty"] * product["standard_price"]
            print("_get_journalitems_from_pickling...14...amount==", amount)

            # Debit line → expense account
            journal_lines.append({
                "Description": product["name"],
                "AccountCode": XERO_AccountCode_COGS,
                "LineAmount": amount,   # ✅ 必須有
                "TaxType": "NONE"
            })

            # Credit line → inventory account
            journal_lines.append({
                "Description": product["name"],
                "AccountCode": XERO_AccountCode_Inventory,   # Inventory account
                "LineAmount": -amount,  # ✅ Credit 用負數
                "TaxType": "NONE"
            })

        print("_get_journalitems_from_pickling...20...journal_lines==", journal_lines)

        return journal_lines



    def delete_all_invoices(self, access_token, tenant_id):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # 1. 拉全部 Invoice (summary only)
        r = requests.get(XERO_INVOICE_URL, headers=headers)
        invoices = r.json().get("Invoices", [])
        print("delete_all_invoices...0....invoices==", invoices)
        if not invoices:
            print("No invoices found to delete/void.")
            return

        for inv in invoices:
            inv_id = inv["InvoiceID"]
            inv_num = inv["InvoiceNumber"]
            status = inv["Status"]
            ts = time.time_ns()

            print("delete_all_invoices...1....")

            if status in ("DRAFT", "AUTHORISED", "SUBMITTED"):
                # Step 0: GET full invoice by ID
                get_url = f"{XERO_INVOICE_URL}/{inv_id}"
                full_resp = requests.get(get_url, headers=headers)
                full_data = full_resp.json()
                full_inv = full_data.get("Invoices", [])[0]

                # Step 1: 改 InvoiceNumber (完整 payload)
                update_payload = {
                    "Invoices": [{
                        "InvoiceID": inv_id,
                        "Type": full_inv["Type"],
                        "Contact": full_inv["Contact"],
                        "Date": full_inv["Date"],
                        "DueDate": full_inv["DueDate"],
                        "InvoiceNumber": f"{full_inv['InvoiceNumber']}-REV-{ts}",
                        "CurrencyCode": full_inv["CurrencyCode"],
                        "LineItems": full_inv["LineItems"],   # 由 GET by ID 拉返完整
                        "Total": full_inv["Total"],
                        "TotalTax": full_inv["TotalTax"],
                        "Status": full_inv["Status"],
                        "Reference": full_inv.get("Reference", "")
                    }]
                }

                print("delete_all_invoices...2....")

                resp1 = requests.post(XERO_INVOICE_URL, json=update_payload, headers=headers)
                print("delete_all_invoices...3....")

                if resp1.status_code not in (200, 201):
                    print("Error renaming invoice:", resp1.status_code, resp1.text)
                    continue

                print("delete_all_invoices...4....")

                # Step 2: VOID Invoice (minimal payload)
                void_payload = {
                    "Invoices": [{
                        "InvoiceID": inv_id,
                        "InvoiceNumber": f"{full_inv['InvoiceNumber']}-REV-{ts}",
                        "Type": full_inv["Type"],
                        "Status": "VOIDED"
                    }]
                }

                print("delete_all_invoices...5....")

                resp2 = requests.post(XERO_INVOICE_URL, json=void_payload, headers=headers)
                print("delete_all_invoices...6....")

                if resp2.status_code in (200, 201):
                    print(f"Successfully voided invoice {inv_num} with REV key!")
                else:
                    print("Error voiding invoice:", resp2.status_code, resp2.text)
   
            else:
                print(f"Skip invoice {inv_num} with status {status}")



    def delete_all_COGS(self, access_token, tenant_id):

        headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # 1. Fetch all Manual Journals
        r = requests.get(XERO_MANUAL_JOURNAL_URL, headers=headers)
        journals = r.json().get("ManualJournals", [])

        if not journals:
            print("No manual journals found to clear.")
            return

        for jnl in journals:
            jnl_id = jnl["ManualJournalID"]
            status = jnl["Status"]
            orig_ref = jnl.get("Reference", "")
            ts = time.time_ns()

            if status in ("DRAFT", "POSTED"):
                # Clean up old stacked timestamps from previous test runs if any exist
                base_ref = orig_ref.split("-REV-")[0] if orig_ref else jnl_id
                renamed_ref = f"{base_ref}-REV-{ts}"

                # -------------------------------------------------------------
                # STEP 1: Update the Reference field ONLY (Keep current status)
                # -------------------------------------------------------------
                update_payload = {
                    "ManualJournals": [{
                        "ManualJournalID": jnl_id,
                        "Reference": renamed_ref,
                        "Status": status # Maintain status so it processes field adjustments
                    }]
                }
                
                resp1 = requests.post(XERO_MANUAL_JOURNAL_URL, json=update_payload, headers=headers)
                if resp1.status_code not in (200, 201):
                    print(f"Error renaming journal {jnl_id}:", resp1.status_code, resp1.text)
                    continue
                else:
                    print(f"[Step 1 Success] Journal renamed to: {renamed_ref}")

                # -------------------------------------------------------------
                # STEP 2: Permanent Void (Xero locks entries down here)
                # -------------------------------------------------------------
                void_payload = {
                    "ManualJournals": [{
                        "ManualJournalID": jnl_id,
                        "Reference": renamed_ref,
                        "Status": "VOIDED"
                    }]
                }
                
                resp2 = requests.post(XERO_MANUAL_JOURNAL_URL, json=void_payload, headers=headers)
                if resp2.status_code in (200, 201):
                    print(f"[Step 2 Success] Successfully voided journal reference {renamed_ref}!")
                else:
                    print(f"Error voiding journal {renamed_ref}:", resp2.status_code, resp2.text)
            else:
                print(f"Skip journal {jnl_id} with status {status}")



    def update_sale_order_sync_status(self, order_id, success=True):
        
        vals = {}
        if success:
            vals = {
                "post_sync": True,
                "sync": False,
                "acct_sync_datetime": datetime.datetime.now()
            }
        else:
            vals = {
                "pre_sync": True,
                "sync": False,
                "post_sync": False,
            }
        self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "sale.order", "write", [[order_id], vals]
        )


    def update_COGS_sync_status(self, picking_id, manual_journal_id=None, success=True):
        vals = {}
        if success:
            vals = {
                "post_sync": True,
                "sync": False,
                "acct_sync_datetime": datetime.datetime.now(),
                "acct_sync_id": manual_journal_id  # ✅ 儲存 ManualJournalID
            }
        else:
            vals = {
                "pre_sync": True,
                "sync": False,
                "post_sync": False,
                "acct_sync_id": manual_journal_id  # ❗ 即使失敗都存返，方便 rerun void
            }

        self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "stock.picking", "write", [[picking_id], vals]
        )





    def pull_odoo_sale_orders_and_pickings(self):

        try:
            # ─── STEP 1: GET LATEST SALE ORDERS BY CLIENT REF ───
            # Notice the outer [ ] enclosing all 3 inner parameters
            so_groups = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "sale.order", "read_group",
                [
                    [("post_sync", "=", False)],     # Positional 1: Domain
                    ["id:max", "client_order_ref"],  # Positional 2: Fields to aggregate
                    ["client_order_ref"]             # Positional 3: Groupby array
                ],
                {"lazy": False}                      # Keyword arguments dict
            )

            print("so_groups==", so_groups)

            so_ids = []
            for g in so_groups:
                target_id = g.get("id") or g.get("id_max")
                if target_id:
                    so_ids.append(target_id)

            if not so_ids:
                return {"status": "success", "sale_orders": [], "pickings": []}

            print("so_ids == ", so_ids)

            # Read the full details of ONLY the latest Sale Orders
            sale_orders = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "sale.order", "read", 
                [so_ids],                             # Position 1: IDs array wrapped in a list
                {"fields": ["id", "name", "client_order_ref", "partner_id", "date_order",
                            "order_line", "state", "amount_total", "amount_tax", "currency_id"]}
            )

            print("sale_orders == ", sale_orders)

            # ─── STEP 2: CHAIN PICKINGS TO LATEST SO NAMES ───
            latest_so_names = [so["name"] for so in sale_orders if so.get("name")]
            if not latest_so_names:
                return {"status": "success", "sale_orders": [], "pickings": []}

            print("latest_so_names == ", latest_so_names)

            # STEP 2b: 清理舊 pickings (避免重複 push)
            old_pickings = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "stock.picking", "search_read",
                [[("origin", "in", latest_so_names), ("post_sync", "=", True)]],
                {"fields": ["id", "origin"]}
            )

            print("old_pickings == ", old_pickings)

            
            # If there are old pickings, clear them out
            for pk in old_pickings:
                self.models.execute_kw(
                    ODOO_DB, self.uid, self.odoo_pass,
                    "stock.picking", "write", 
                    [[pk["id"]], {"active": False}]  # Correctly nested args array
                )

            # Query all pickings belonging to these specific live names
            pickings = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "stock.picking", "search_read",
                [[("post_sync", "=", False), ("origin", "in", latest_so_names)]],
                {"fields": ["id", "origin", "scheduled_date", "date_done", "move_ids", "state", "picking_type_id"]}
            )

            print("\n\n---> pickings == ", pickings)



            # ─── STEP 3: BUILD TRANSFORMATION MAPS ───
            sale_order_map = {}
            for pk in pickings:
                sale_order_map.setdefault(pk["origin"], []).append(pk)

            print("\n\nsale_order_map == ", sale_order_map)

            sale_order_payloads = []
            picking_payloads = []

            for so in sale_orders:
                print("\nsale_orders --> so == ", so)
                pk_list = sale_order_map.get(so["name"], [])

                print("\npk_list == ", pk_list)

                if not pk_list:
                    print("\not pk_list continue ", pk_list)
                    continue

                client_ref = so.get("client_order_ref") or f"SO{so['id']}"

                print("\nclient_ref == ", client_ref)

                for pk in pk_list:
                    print("\npk_list --> pk ...0...")
                    print("\npk_list --> pk == ", pk)

                    invoice_number = str(client_ref)  # 唯一用 client_order_ref
                    print("\npk_list --> pk ...1...")
                    journal_number = f"{client_ref}00000{pk['id']}"
                    print("\npk_list --> pk ...2...")
                    journel_reference = f"{client_ref}-PK{pk['id']}"
                    print("\npk_list --> pk ...3...")

                    line_items = self._get_lineitems_from_sale_order(so)
                    print("\npk_list --> pk ...4...", pk)
                                          
                    journal_lines = self._get_journalitems_from_pickling(pk)
                    print("\npk_list --> pk ...5...")
                    order_id = so["id"]
                    print("\npk_list --> pk ...6...")
                     
                    print("\npk_list --> pk ...10...")

                    # Invoice payload
                    sale_order_payloads.append({
                            "order_id": order_id,
                            "Type": "ACCREC",
                            "Contact": {"Name": so["partner_id"][1]},
                            "Date": so["date_order"],
                            "DueDate": so["date_order"],
                            "InvoiceNumber": invoice_number,
                            "CurrencyCode": so["currency_id"][1] if so.get("currency_id") else "HKD",
                            "LineItems": line_items,
                            "Total": so["amount_total"],
                            "TotalTax": so["amount_tax"], 
                            "Status": "AUTHORISED" if so["state"] == "sale" else "VOIDED",
                            "Reference": invoice_number
                    })

                    print("\npk_list --> pk ...20...")

                    # Journal payload
                    picking_payloads.append({
                            "order_id": order_id,
                            "picking_id": pk["id"],
                            "Narration": f"COGS for Picking {pk['id']} ({pk['picking_type_id'][1]})",
                            "Date": pk.get("date_done") or pk["scheduled_date"],
                            "JournalNumber": journal_number,
                            "Reference": journel_reference,
                            "JournalLines": journal_lines,
                            "Status": "POSTED" if pk["state"] == "done" else "VOIDED"
                    })

                    print("\npk_list --> pk ...30...")

                    print("\n-----loop sale_order_payloads ", sale_order_payloads)
                    print("\n-----loop picking_payloads ", picking_payloads)

            print("\n\nsale_order_payloads == ", sale_order_payloads)
            print("\n\npicking_payloads == ", picking_payloads)

            final_result = {"status": "success", "sale_orders": sale_order_payloads, "pickings": picking_payloads}
            
            print("\n\nfinal_result == ", final_result)
            
            return final_result

        except Exception as e:
            logger.error(f"Sync failed: {str(e)}")
            return {"status": "error", "message": str(e)}


  
     


    def push_sale_orders_to_xero(self, payloads, access_token, tenant_id):

        headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        for payload in payloads:
            invoice = payload 
            invoice_number = invoice["InvoiceNumber"]
            order_id = payload.get("order_id")   # 真正 Odoo sale.order.id

            # 查有冇已存在 Invoice
            # check_url = f"{XERO_INVOICE_URL}?where=InvoiceNumber='{invoice_number}'"
            check_url = (
                f"{XERO_INVOICE_URL}?where=InvoiceNumber=='{invoice_number}' AND Status!=\"VOIDED\""
            )

            check_resp = requests.get(check_url, headers=headers)
            data = check_resp.json()

            if data.get("Invoices"):
                invoice_id = data["Invoices"][0]["InvoiceID"]
                invoice["InvoiceID"] = invoice_id
                update_payload = {"Invoices": [invoice]}
                response = requests.post(XERO_INVOICE_URL, json=update_payload, headers=headers)
            else:
                response = requests.put(XERO_INVOICE_URL, json=payload, headers=headers)

            print("\n====\nupdate_payload...response == ", response.json())
            print("\n====\nupdate_payload...response.status_code == ", response.status_code)

            # 判斷邏輯
            if response.status_code in (200, 201):
                self.update_sale_order_sync_status(order_id, success=True)

            elif response.status_code == 400:
                 
                # CASE BY CASE BASIS, need manual troubleshooting
                self.update_sale_order_sync_status(order_id, success=False)
                logger.error(f"manual troubleshooting for order {order_id}")

            elif response.status_code >= 500:
                # 網絡/伺服器錯誤 → 留待重試
                self.update_sale_order_sync_status(order_id, success=False)

            else:
                # 其他情況 → 當失敗
                self.update_sale_order_sync_status(order_id, success=False)




    def push_stock_pickings_to_xero(self, payloads, access_token, tenant_id):

        headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        for payload in payloads:
            journal_number = payload["JournalNumber"]
            picking_id = payload.get("picking_id") 

            print("push_stock_pickings_to_xero...0...journal_number==", journal_number)
            print("push_stock_pickings_to_xero...0...picking_id==", picking_id)

            # STEP 1: 從 Odoo 讀返之前存嘅 ManualJournalID
            picking = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "stock.picking", "read",
                [[picking_id]],
                {"fields": ["acct_sync_id"]}
            )

            print("push_stock_pickings_to_xero...1...stock.picking::read(picking==", picking)

            if picking:
                existing_id = picking[0].get("acct_sync_id")
                print("push_stock_pickings_to_xero...10...existing_id==", existing_id)
            else:
                existing_id = False
                print("push_stock_pickings_to_xero...11...existing_id is None")


            # STEP 2: 如果有舊 ManualJournalID → 先 VOID 舊 record
            if existing_id and existing_id != "00000000-0000-0000-0000-000000000000":
                print("push_stock_pickings_to_xero...20...void_payload...")
                void_payload = {
                    "ManualJournals": [{
                        "ManualJournalID": existing_id,
                        "Status": "VOIDED"
                    }]
                }

                print("push_stock_pickings_to_xero...21...void_payload==", void_payload)

                void_resp = requests.post(XERO_MANUAL_JOURNAL_URL, json=void_payload, headers=headers)

                print("push_stock_pickings_to_xero...30...requests.post...void_payload==", void_resp.json())
 

            print("push_stock_pickings_to_xero...40...")

            try:
          
                response = requests.put(XERO_MANUAL_JOURNAL_URL, json=payload, headers=headers)

                print("push_stock_pickings_to_xero...41...requests.put, response.json() == ", response.json())
    

                print("\n====\nupdate_payload...response == ", response.json())
                print("\n====\nupdate_payload...response.status_code == ", response.status_code)

                # STEP 4: 判斷邏輯
                if response.status_code in (200, 201):
                    resp_json = response.json()
                    journals = resp_json.get("ManualJournals", [])
                    if journals:
                        new_id = journals[0].get("ManualJournalID")
                        # 儲存新 ManualJournalID 入 Odoo
                        self.update_COGS_sync_status(picking_id, new_id, success=True)
                elif response.status_code == 400:
                    # Validation fail → 留待人工檢查
                    #self.update_COGS_sync_status(picking_id, None, success=False)
                    logger.error(f"manual troubleshooting for picking {journal_number}")
                elif response.status_code >= 500:
                    # 網絡/伺服器錯誤 → 留待重試
                    self.update_COGS_sync_status(picking_id, None, success=False)
                else:
                    # 其他情況 → 當失敗
                    self.update_COGS_sync_status(picking_id, None, success=False)



            except Exception as e:   
                print(f"Exception occurred: {e}")
                self.update_COGS_sync_status(picking_id, None, success=False)


             

        
    def sync_all_transactions(self, access_token, tenant_id):
        #
        payloads = self.pull_odoo_sale_orders_and_pickings()
        # 
        sale_orders = payloads.get("sale_orders", []) 
        self.push_sale_orders_to_xero(sale_orders, access_token, tenant_id)
        #
        pickings = payloads.get("pickings", [])   
        print("pickings == ", pickings)

        self.push_stock_pickings_to_xero(pickings, access_token, tenant_id)
     
        return {"status": "completed"}
