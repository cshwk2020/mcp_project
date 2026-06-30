import xmlrpc.client
from mcp_project.config import ODOO_BASE_URL, ODOO_DB
from mcp_project.mcp_shared.vault_util import VaultUtil
from mcp_project.mcp_shared.safe_utils import safe_dict, safe_datetime, safe_val, safe_float

class MCPOdooClient:

    def __init__(self):
        vault = VaultUtil()
        self.odoo_user = vault.get_odoo_user()
        self.odoo_pass = vault.get_odoo_pass()
        common = xmlrpc.client.ServerProxy(f"{ODOO_BASE_URL}/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(ODOO_DB, self.odoo_user, self.odoo_pass, {})
        self.models = xmlrpc.client.ServerProxy(f"{ODOO_BASE_URL}/xmlrpc/2/object", allow_none=True)
        self.db = ODOO_DB

    # ── Warehouse ──────────────────────────────
    def get_warehouse_context(self, warehouse_code):
        recs = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "stock.warehouse", "search_read",
            [[("code", "=", warehouse_code)]],
            {"fields": ["id", "lot_stock_id"], "limit": 1}
        )
        if not recs:
            return None, None, None
        warehouse_id = recs[0]["id"]
        lot_stock_id = recs[0]["lot_stock_id"][0] if recs[0].get("lot_stock_id") else None
        picking_type = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "stock.picking.type", "search_read",
            [[("warehouse_id", "=", warehouse_id), ("code", "=", "outgoing")]],
            {"fields": ["id"], "limit": 1}
        )
        delivery_type_id = picking_type[0]["id"] if picking_type else None
        return warehouse_id, lot_stock_id, delivery_type_id



    def delete_all_so(self):
        """
        Cancel then delete all Sales Orders in Odoo.
        """
        # 找出所有非 cancel 嘅 SO
        so_ids = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'sale.order', 'search',
            [[('state', '!=', 'cancel')]]
        )

        if not so_ids:
            return {"status": "success", "deleted": []}

        # 先 cancel
        self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'sale.order', 'action_cancel',
            [so_ids]
        )

        # 再 unlink
        self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'sale.order', 'unlink',
            [so_ids]
        )

        return {"status": "success", "deleted": so_ids}


    def delete_all_po(self):
        """
        Cancel then delete all Purchase Orders in Odoo (purchase.order).
        """
        po_ids = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'purchase.order', 'search',
            [[('state', '!=', 'cancel')]]
        )

        if not po_ids:
            return {"status": "success", "deleted": []}

        # Cancel orders (force non-None return)
        _ = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'purchase.order', 'button_cancel',
            [po_ids]
        ) or True

        # Delete orders (force non-None return)
        _ = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'purchase.order', 'unlink',
            [po_ids]
        ) or True

        return {"status": "success", "deleted": po_ids}



    def get_customer_location(self):
        locs = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "stock.location", "search_read",
            [[("usage", "=", "customer")]],
            {"fields": ["id"], "limit": 1}
        )
        return locs[0]["id"] if locs else None

    # ── Partner ────────────────────────────────
    def get_or_create_partner(self, order):
        customer = order.get("customer", {})
        email = customer.get("email")
        partner_ids = []
        if email:
            partner_ids = self.models.execute_kw(
                self.db, self.uid, self.odoo_pass,
                "res.partner", "search",
                [[("email", "=", email)]]
            )
        customer_location_id = self.get_customer_location()
        if partner_ids:
            partner_id = partner_ids[0]
            self.models.execute_kw(
                self.db, self.uid, self.odoo_pass,
                "res.partner", "write",
                [[partner_id], {
                    "property_stock_customer": customer_location_id,
                    "name": f"{customer.get('first_name','')} {customer.get('last_name','')}".strip() or email,
                    "phone": customer.get("phone"),
                    "street": customer.get("default_address", {}).get("address1"),
                    "street2": customer.get("default_address", {}).get("address2"),
                    "city": customer.get("default_address", {}).get("city"),
                    "zip": customer.get("default_address", {}).get("zip"),
                    "country_id": customer.get("default_address", {}).get("country_code"),
                }]
            )
            return partner_id
        partner_id = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "res.partner", "create",
            [{
                "name": f"{customer.get('first_name','')} {customer.get('last_name','')}".strip() or email,
                "email": email,
                "phone": customer.get("phone"),
                "street": customer.get("default_address", {}).get("address1"),
                "street2": customer.get("default_address", {}).get("address2"),
                "city": customer.get("default_address", {}).get("city"),
                "zip": customer.get("default_address", {}).get("zip"),
                "country_id": customer.get("default_address", {}).get("country_code"),
                "type": "contact",
            }]
        )
        return partner_id

    # ── Orders ─────────────────────────────────
    def revoke_order(self, order_ref, delivery_type_id):
        existing = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "sale.order", "search",
            [[("client_order_ref", "=", order_ref), ("state", "!=", "cancel")]]
        )
        if not existing:
            return
        sale_order_id = existing[0]
        self.models.execute_kw(self.db, self.uid, self.odoo_pass,
                               "sale.order", "action_cancel", [[sale_order_id]])

 
    def create_order(self, order_head, order_lines, delivery_type_id):

        sale_order_id = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "sale.order", "create", [order_head]
        )

        for line in order_lines:
            line["order_id"] = sale_order_id
            self.models.execute_kw(
                self.db, self.uid, self.odoo_pass,
                "sale.order.line", "create", [line]
            )

        # confirm order
        self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "sale.order", "action_confirm", [[sale_order_id]]
        )

        # validate pickings
        pickings = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "stock.picking", "search",
            [[("sale_id", "=", sale_order_id), ("state", "not in", ["done", "cancel"])]]
        )
        for pid in pickings:
            self.models.execute_kw(
                self.db, self.uid, self.odoo_pass,
                "stock.picking", "action_assign", [[pid]]
            )
            self.models.execute_kw(
                self.db, self.uid, self.odoo_pass,
                "stock.picking", "button_validate", [[pid]]
            )

        # 🚨 instead of action_create_invoice → mark invoiced qty same as delivered
        line_ids = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "sale.order.line", "search",
            [[("order_id", "=", sale_order_id)]]
        )
        if line_ids:
            lines = self.models.execute_kw(
                self.db, self.uid, self.odoo_pass,
                "sale.order.line", "read",
                [line_ids, ["qty_delivered", "qty_invoiced"]]
            )
            for idx, ln in zip(line_ids, lines):
                delivered = ln["qty_delivered"]
                self.models.execute_kw(
                    self.db, self.uid, self.odoo_pass,
                    "sale.order.line", "write",
                    [[idx], {"qty_invoiced": delivered}]
                )

        return sale_order_id


    # ── Currency ───────────────────────────────
    def get_company_currency(self):
        company = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "res.company", "search_read",
            [[]],
            {"fields": ["currency_id"], "limit": 1}
        )
        return company[0]["currency_id"][1] if company else "USD"

    def get_currency_id(self, currency_name):
        rec = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "res.currency", "search_read",
            [[("name", "=", currency_name)]],
            {"fields": ["id"], "limit": 1}
        )
        return rec[0]["id"] if rec else None

    def convert_currency(self, amount, from_cur, to_cur):
        if from_cur == to_cur:
            return safe_float(amount)
        rate_rec = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "res.currency.rate", "search_read",
            [[("currency_id.name", "=", from_cur)]],
            {"fields": ["rate"], "limit": 1}
        )
        if not rate_rec:
            # fallback 1:1
            return safe_float(amount)
        rate = rate_rec[0]["rate"]
        return safe_float(amount) * rate

    # ── Product ────────────────────────────────
    def find_product_by_sku(self, sku):
        if not sku:
            return None
        product_ids = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "product.product", "search",
            [[("default_code", "=", sku)]]
        )
        return product_ids[0] if product_ids else None

     


    def get_vendor_contact(self, partner_id):
        """Fetch vendor contact info from Odoo partner record."""
        vendor = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'res.partner', 'read',
            [partner_id],
            {'fields': ['id', 'name', 'email', 'phone', 'street', 'city', 'zip', 'country_id', 'ref']}
        )[0]

        return {
            "id": vendor["id"],
            "name": vendor.get("name") or "",
            "email": vendor.get("email") or "",
            "phone": vendor.get("phone") or "",
            "ref": vendor.get("ref") or "",   # ✅ 存 Xero ContactID
            "address": {
                "street": vendor.get("street") or "",
                "city": vendor.get("city") or "",
                "zip": vendor.get("zip") or "",
                "country": vendor["country_id"][1] if vendor.get("country_id") else ""
            }
        }

    def get_contacts(self, limit=200):
        """Fetch active contacts (vendors/customers) from Odoo."""
        contact_ids = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'res.partner', 'search',
            [[['active', '=', True]]],
            {'limit': limit}
        )

        if not contact_ids:
            return []

        contacts = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'res.partner', 'read',
            [contact_ids],
            {'fields': ['id', 'name', 'email', 'phone', 'street', 'city', 'zip', 'country_id', 'ref']}
        )

        results = []
        for c in contacts:
            results.append({
                "id": c["id"],
                "name": c.get("name") or "",
                "email": c.get("email") or "",
                "phone": c.get("phone") or "",
                "ref": c.get("ref") or "",   # ✅ 存 Xero ContactID
                "address": {
                    "street": c.get("street") or "",
                    "city": c.get("city") or "",
                    "zip": c.get("zip") or "",
                    "country": c["country_id"][1] if c.get("country_id") else ""
                }
            })
        return results


    def get_products(self, ids=None):
        """
        Fetch products from Odoo.
        - If ids list is provided and non-empty, only fetch those products.
        - If ids is None or empty, fetch all active + sold products.
        """
        if ids and len(ids) > 0:
            # 直接用指定 ids
            all_ids = ids
        else:
            # 拉全部 active products
            active_ids = self.models.execute_kw(
                self.db, self.uid, self.odoo_pass,
                'product.product', 'search',
                [[['active', '=', True]]]
            )

            # 拉所有 sale order line 用過嘅 products
            sale_line_ids = self.models.execute_kw(
                self.db, self.uid, self.odoo_pass,
                'sale.order.line', 'search_read',
                [[['order_id.state', 'in', ['sale', 'done']]]],
                {'fields': ['product_id']}
            )
            order_product_ids = list({sl['product_id'][0] for sl in sale_line_ids if sl.get('product_id')})

            # 合併 active + sold
            all_ids = list(set(active_ids) | set(order_product_ids))

        # 拉出需要嘅欄位
        products = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'product.product', 'read',
            [all_ids],
            {'fields': [
                'default_code', 'name', 'description',
                'list_price', 'standard_price', 'sync_status'
            ]}
        )

        # 返回乾淨 dict
        return [
            {
                "id": p.get("id"),
                "code": p.get("default_code") or "",
                "name": p.get("name") or "",
                "description": p.get("description") or "",
                "sale_price": p.get("list_price", 0.0),
                "purchase_price": p.get("standard_price", 0.0),
                "sync_status": p.get("sync_status")
            }
            for p in products
        ]



    def get_purchase_orders(self, limit=100):
        """Fetch active purchase orders from Odoo with line items."""
        po_ids = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'purchase.order', 'search',
            [[['state', 'in', ['purchase', 'done']]]],
            {'limit': limit}
        )

        if not po_ids:
            return []

        pos = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'purchase.order', 'read',
            [po_ids],
            {'fields': ['id', 'name', 'partner_id', 'date_order', 'order_line', 'sync_status']}
        )

        results = []
        for po in pos:
            line_items = []
            if po.get("order_line"):
                lines = self.models.execute_kw(
                    self.db, self.uid, self.odoo_pass,
                    'purchase.order.line', 'read',
                    [po["order_line"]],
                    {'fields': ['product_id', 'name', 'product_qty', 'price_unit']}
                )
                for ln in lines:
                    product_code = ""
                    if ln.get("product_id"):
                        prod = self.models.execute_kw(
                            self.db, self.uid, self.odoo_pass,
                            'product.product', 'read',
                            [ln["product_id"][0]],
                            {'fields': ['default_code']}
                        )
                        product_code = prod[0].get("default_code") or ""

                    line_items.append({
                        "item_code": product_code,
                        "description": ln.get("name") or "",
                        "quantity": ln.get("product_qty", 0),
                        "unit_price": ln.get("price_unit", 0),
                        "account_code": "630"
                    })

            # 拉 vendor record，取 ref
            vendor = self.get_vendor_contact([po["partner_id"][0]]) if po.get("partner_id") else None
            vendor_ref = vendor.get("ref") if vendor else ""

            results.append({
                "id": po["id"],
                "po_number": po["name"],
                "vendor_name": po["partner_id"][1] if po.get("partner_id") else "",
                "partner_id": po["partner_id"][0] if po.get("partner_id") else None,
                "vendor_ref": vendor_ref,   # 存 Xero ContactID in ref
                "date": po.get("date_order"),
                "sync_status": po["sync_status"],
                "line_items": line_items
            })

        return results


    def get_po_state(self, po_id):
        """
        Check if a Purchase Order is billed and received in Odoo.
        Returns dict: {"billed": bool, "received": bool}
        """
        po_data = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "purchase.order", "read",
            [[po_id], ["invoice_status", "picking_ids"]]
        )[0]

        # 判斷是否已經有 Bill
        billed = (po_data.get("invoice_status") == "invoiced")

        # 判斷是否有收貨單
        received = bool(po_data.get("picking_ids"))

        return {"billed": billed, "received": received}




    def get_sales_orders(self, limit=100):
        """Fetch active sales orders from Odoo with line items."""
        so_ids = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'sale.order', 'search',
            [[['state', 'in', ['sale', 'done']]]],  # only confirmed/done SOs
            {'limit': limit}
        )

        if not so_ids:
            return []

        sos = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            'sale.order', 'read',
            [so_ids],
            {'fields': ['id', 'name', 'partner_id', 'date_order', 'validity_date', 'order_line', 'sync_status']}
        )

        results = []
        for so in sos:
            line_items = []
            if so.get("order_line"):
                lines = self.models.execute_kw(
                    self.db, self.uid, self.odoo_pass,
                    'sale.order.line', 'read',
                    [so["order_line"]],
                    {'fields': ['product_id', 'name', 'product_uom_qty', 'price_unit']}
                )
                for ln in lines:
                    product_code = ""
                    if ln.get("product_id"):
                        prod = self.models.execute_kw(
                            self.db, self.uid, self.odoo_pass,
                            'product.product', 'read',
                            [ln["product_id"][0]],
                            {'fields': ['default_code']}
                        )
                        product_code = prod[0].get("default_code") or ""

                    line_items.append({
                        "item_code": product_code,   # ✅ 必須傳 ItemCode → Xero tracked inventory
                        "description": ln.get("name") or "",
                        "quantity": ln.get("product_uom_qty", 0),
                        "unit_price": ln.get("price_unit", 0),
                        "account_code": "200"  # default sales revenue account
                    })

            results.append({
                "id": so["id"],
                "so_number": so["name"],
                "customer_name": so["partner_id"][1] if so.get("partner_id") else "",
                "partner_id": so["partner_id"][0] if so.get("partner_id") else None,
                "date": so.get("date_order"),
                "due_date": so.get("validity_date"),
                "sync_status": so.get("sync_status"),
                "line_items": line_items
            })

        return results


 
    def mark_po_received(self, po_id):
        """
        Mark a Purchase Order as received in Odoo.
        This will validate the receipt picking linked to the PO.
        """
        # 找到 PO 對應嘅收貨 picking
        picking_ids = self.models.execute_kw(
            self.db, self.uid, self.odoo_pass,
            "stock.picking", "search",
            [[("purchase_id", "=", po_id), ("state", "not in", ["done", "cancel"])]]
        )

        for pid in picking_ids:
            # assign + validate picking
            self.models.execute_kw(
                self.db, self.uid, self.odoo_pass,
                "stock.picking", "action_assign", [[pid]]
            )
            self.models.execute_kw(
                self.db, self.uid, self.odoo_pass,
                "stock.picking", "button_validate", [[pid]]
            )

        return {"status": "success", "po_id": po_id, "pickings": picking_ids}
