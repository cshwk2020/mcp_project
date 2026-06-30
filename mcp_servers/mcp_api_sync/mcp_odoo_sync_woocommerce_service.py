import xmlrpc.client
import logging
from mcp_project.mcp_shared.vault_util import VaultUtil
from mcp_project.config import ODOO_BASE_URL, ODOO_DB
from mcp_project.mcp_shared.safe_utils import safe_dict, safe_datetime, safe_val, safe_str, safe_int, safe_float

logger = logging.getLogger(__name__)


class MCPOdooSyncWoocommerceService:
    def __init__(self, odoo_client):
        self.service_name = "Odoo Sync Woocommerce MCP Server"
        self.odoo_client = odoo_client
        _vault = VaultUtil()
        self.odoo_user = _vault.get_odoo_user()
        self.odoo_pass = _vault.get_odoo_pass()
        self.uid, self.models = self._get_models(self.odoo_user, self.odoo_pass)

    def get_tools_schema(self):
        return [
            {
                "name": "sync_woocommerce_orders_to_odoo",
                "description": "Manual sync WooCommerce orders into Odoo.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "orders": {"type": "array"},
                        "warehouse": {"type": "string", "default": "woo_wh"}
                    },
                    "required": ["orders"]
                }
            }
        ]

    # Helper: get warehouse + lot_stock_id + delivery_type_id
    def _get_warehouse_context(self, warehouse_code):
        recs = self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "stock.warehouse", "search_read",
            [[("code", "=", warehouse_code)]],
            {"fields": ["id", "lot_stock_id"], "limit": 1}
        )
        if not recs:
            return None, None, None

        warehouse_id = recs[0]["id"]
        lot_stock_id = recs[0]["lot_stock_id"][0] if recs[0].get("lot_stock_id") else None

        picking_type = self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "stock.picking.type", "search_read",
            [[("warehouse_id", "=", warehouse_id), ("code", "=", "outgoing")]],
            {"fields": ["id"], "limit": 1}
        )
        delivery_type_id = picking_type[0]["id"] if picking_type else None

        return warehouse_id, lot_stock_id, delivery_type_id

    def _get_customer_location(self):
        # Odoo 預設有一個 "Customer" location
        locs = self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "stock.location", "search_read",
            [[("usage", "=", "customer")]],
            {"fields": ["id"], "limit": 1}
        )
        return locs[0]["id"] if locs else None

    # WooCommerce sync
    def sync_woocommerce_orders_to_odoo(self, orders, warehouse_code="whwoo"):
        warehouse_id, lot_stock_id, delivery_type_id = self._get_warehouse_context(warehouse_code)
        return self._sync_pipeline(
            orders,
            warehouse_id,
            lot_stock_id,
            delivery_type_id,
            source="woocommerce",
            # Expects 4 positional arguments from pipeline calls
            map_head=lambda o, wid, lid, did: self._map_order_head(o, wid, lid),
            map_lines=self._map_order_lines
        )

    def _revoke_order(self, order_ref, delivery_type_id):
        # ── STEP 1: Find existing sale order (not cancelled) ────────
        existing = self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "sale.order", "search",
            [[("client_order_ref", "=", order_ref), ("state", "!=", "cancel")]]
        )
        print("DEBUG...10...search existing == ", order_ref, existing)

        if existing and len(existing) > 0:
            sale_order_id = existing[0]
            print("DEBUG...11...sale_order_id == ", sale_order_id)

            # Read current state
            so_data = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "sale.order", "read",
                [[sale_order_id], ["state", "picking_ids"]]
            )[0]
            print("DEBUG...12...sale_order...so_data == ", so_data)

            picking_ids = so_data["picking_ids"]
            print("DEBUG...13...picking_ids == ", picking_ids)

            # ── STEP 2: Reverse all existing pickings ───────────────
            for pid in picking_ids:
                picking = self.models.execute_kw(
                    ODOO_DB, self.uid, self.odoo_pass,
                    "stock.picking", "read",
                    [[pid], ["state", "origin", "location_id", "location_dest_id", "partner_id"]]
                )[0]
                print("DEBUG...14...picking == ", picking)

                if picking["state"] == "done":
                    print("DEBUG...15...picking state == done")

                    # Read sale order name
                    so_name = self.models.execute_kw(
                        ODOO_DB, self.uid, self.odoo_pass,
                        "sale.order", "read",
                        [[sale_order_id], ["name"]]
                    )[0]["name"]

                    # Always create return picking
                    return_picking_id = self.models.execute_kw(
                        ODOO_DB, self.uid, self.odoo_pass,
                        "stock.picking", "create", [{
                            "origin": f"RETURN-{order_ref}-{so_name}",
                            "picking_type_id": delivery_type_id,
                            "location_id": picking["location_dest_id"][0],
                            "location_dest_id": picking["location_id"][0],
                            "partner_id": picking["partner_id"][0] if picking["partner_id"] else False,
                            "sale_id": sale_order_id,
                        }]
                    )
                    print("DEBUG...17... reverse picking......return_picking_id == ", return_picking_id)

                    # Reverse moves
                    move_ids = self.models.execute_kw(
                        ODOO_DB, self.uid, self.odoo_pass,
                        "stock.move", "search",
                        [[("picking_id", "=", pid)]]
                    )
                    print("DEBUG...18...Reverse moves......move_ids == ", move_ids)

                    moves = self.models.execute_kw(
                        ODOO_DB, self.uid, self.odoo_pass,
                        "stock.move", "read",
                        [move_ids, ["product_id", "product_uom_qty", "price_unit", "description_picking"]]
                    )
                    print("DEBUG...19...Reverse moves......moves == ", moves)

                    for mv in moves:
                        print("DEBUG...20...Reverse moves......stock.move :: create :: Reverse moves: ...BEFORE...")
                        self.models.execute_kw(
                            ODOO_DB, self.uid, self.odoo_pass,
                            "stock.move", "create", [{
                                "product_id": mv["product_id"][0],
                                "product_uom_qty": mv["product_uom_qty"],
                                "product_uom": 1,
                                "price_unit": mv["price_unit"],
                                "picking_id": return_picking_id,
                                "location_id": picking["location_dest_id"][0],
                                "location_dest_id": picking["location_id"][0],
                                "description_picking": mv["description_picking"],
                            }]
                        )
                        print("DEBUG...20...Reverse moves......stock.move :: create :: Reverse moves: ...AFTER...")

                    # Validate return picking
                    self.models.execute_kw(
                        ODOO_DB, self.uid, self.odoo_pass,
                        "stock.picking", "button_validate", [[return_picking_id]]
                    )
                    print("DEBUG...22...validate REVERSE PICKING...stock.picking :: button_validate (return_picking_id==", return_picking_id)

                elif picking["state"] in ("draft", "waiting", "confirmed", "assigned"):
                    print("DEBUG...51...state (NOT DONE) in (draft/waiting/confirmed/assigned)...==...", picking["state"])
                    self.models.execute_kw(
                        ODOO_DB, self.uid, self.odoo_pass,
                        "stock.picking", "action_cancel", [[pid]]
                    )
                    print("DEBUG...52...CANCEL NON-DONE-PICKING......stock.picking :: action_cancel...BEFORE...")
                    self.models.execute_kw(
                        ODOO_DB, self.uid, self.odoo_pass,
                        "stock.picking", "unlink", [[pid]]
                    )
                    print("DEBUG...52...CANCEL NON-DONE-PICKING......stock.picking :: action_cancel...AFTER...")

            # ── STEP 3: Cancel old sale order ───────────────────────
            print("DEBUG...71...Cancel sale order for leaving AUDIT TRAIL...BEFORE...")
            self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "sale.order", "action_cancel", [[sale_order_id]]
            )
            print("DEBUG...71...Cancel sale order for leaving AUDIT TRAIL...AFTER...")

            # ── STEP 4: Delete old order lines ──────────────────────
            line_ids = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "sale.order.line", "search",
                [[("order_id", "=", sale_order_id)]]
            )
            print("DEBUG...91...search old order lines...", sale_order_id, line_ids)

            if line_ids:
                print("DEBUG...92...KEEP old order lines for audit trail...(line_ids==", line_ids, ")")
                self.models.execute_kw(
                    ODOO_DB, self.uid, self.odoo_pass,
                    "sale.order.line", "write",
                    [line_ids, {"name": "[CANCELLED] "}]
                )
                print("DEBUG...93...mark old order lines as CANCELLED...(line_ids==", line_ids, ")")

    def _create_order(self, order, warehouse_id, lot_stock_id, delivery_type_id, map_head, map_lines):
        # Fixed: Pass all 4 args down into the unified lambda interface
        order_head = map_head(order, warehouse_id, lot_stock_id, delivery_type_id)
        order_lines = map_lines(order)

        sale_order_id = self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "sale.order", "create", [order_head]
        )
        print("DEBUG...101...sale.order...create...(order_head==", order_head, sale_order_id)

        # ── STEP 6: Create new order lines ─────────────────────────
        for line in order_lines:
            line["order_id"] = sale_order_id
            self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "sale.order.line", "create", [line]
            )
            print("DEBUG...102...sale.order.line...create...(line==", line)

        # ── STEP 7: Confirm new sale order ─────────────────────────
        self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "sale.order", "action_confirm", [[sale_order_id]]
        )
        print("DEBUG...111...sale.order...action_confirm...(sale_order_id==", sale_order_id)

        # ── STEP 8: Validate new pickings ──────────────────────────
        new_pickings = self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "stock.picking", "search",
            [[("sale_id", "=", sale_order_id), ("state", "not in", ["done", "cancel"])]]
        )
        print("DEBUG...112...stock.picking::search new_pickings...state not in (done,cancel)......(sale_order_id==", sale_order_id)

        for pid in new_pickings:
            # 🚨 強制更新 picking_type_id，確保用 Woo 倉庫嘅 outgoing type
            self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "stock.picking", "write",
                [[pid], {"picking_type_id": delivery_type_id}]
            )
            print("DEBUG...113...stock.picking...force picking_type_id...(pid==", pid, "delivery_type_id==", delivery_type_id)

            self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "stock.picking", "action_assign", [[pid]]
            )
            self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "stock.picking", "button_validate", [[pid]]
            )

        # ── STEP 9: Mark invoiced qty same as delivered ────────────
        line_ids = self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "sale.order.line", "search",
            [[("order_id", "=", sale_order_id)]]
        )
        print("DEBUG...115...sale.order.line...search...(sale_order_id==", sale_order_id, "line_ids==", line_ids)

        if line_ids:
            lines = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "sale.order.line", "read",
                [line_ids, ["qty_delivered", "qty_invoiced"]]
            )
            print("DEBUG...116...sale.order.line...read...(lines==", lines)

            for idx, ln in zip(line_ids, lines):
                delivered = ln["qty_delivered"]
                self.models.execute_kw(
                    ODOO_DB, self.uid, self.odoo_pass,
                    "sale.order.line", "write",
                    [[idx], {"qty_invoiced": delivered}]
                )
                print("DEBUG...117...sale.order.line...write...(line_id==", idx, "qty_invoiced==", delivered)

        return sale_order_id

    def _sync_pipeline(self, orders, warehouse_id, lot_stock_id, delivery_type_id, source, map_head, map_lines):
        try:
            results = []
            for order in orders:
                order_ref = str(order.get("id"))
                # Fixed: Pass missing context mapping arguments down to lambda
                order_head = map_head(order, warehouse_id, lot_stock_id, delivery_type_id)
                order_lines = map_lines(order)

                order_status = order.get("status")

                # Skip non-settle statuses
                if order_status not in ("completed", "refunded"):
                    print("DEBUG...02...skip order (status not handled)==", order_status)
                    continue

                self._revoke_order(order_ref, delivery_type_id)

                print("DEBUG...100...ALWAYS CANCEL OLD ORDER + CREATE NEW ORDER for audit trail...")

                sale_order_id = self._create_order(order, warehouse_id, lot_stock_id, delivery_type_id, map_head, map_lines)

                results.append({
                    "order_id": order.get("id"),
                    "sale_order_id": sale_order_id,
                    "status": "success"
                })

            return {"status": "success", "results": results}

        except Exception as e:
            logger.error(f"{source} sync failed: {str(e)}")
            return {"error": str(e)}

    def _get_or_create_partner(self, order):
        billing = order.get("billing", {})

        email = billing.get("email")
        partner_ids = []
        if email:
            partner_ids = self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "res.partner", "search",
                [[("email", "=", email)]]
            )

        customer_location_id = self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "stock.location", "search",
            [[("usage", "=", "customer"), ("name", "=", "Customers"), ("active", "=", True)]]
        )[0]

        if partner_ids:
            partner_id = partner_ids[0]
            # 更新 partner 資料（避免舊資料殘留）
            self.models.execute_kw(
                ODOO_DB, self.uid, self.odoo_pass,
                "res.partner", "write",
                [[partner_id], {
                    "property_stock_customer": customer_location_id,
                    "name": f"{billing.get('first_name','')} {billing.get('last_name','')}".strip() or email,
                    "phone": billing.get("phone"),
                    "street": billing.get("address_1"),
                    "street2": billing.get("address_2"),
                    "city": billing.get("city"),
                    "state_id": billing.get("state"),
                    "zip": billing.get("postcode"),
                    "country_id": billing.get("country"),
                }]
            )
            return partner_id

        # 如果唔存在 → 新建 partner
        partner_id = self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "res.partner", "create",
            [{
                "name": f"{billing.get('first_name','')} {billing.get('last_name','')}".strip() or email,
                "email": email,
                "phone": billing.get("phone"),
                "street": billing.get("address_1"),
                "street2": billing.get("address_2"),
                "city": billing.get("city"),
                "state_id": billing.get("state"),
                "zip": billing.get("postcode"),
                "country_id": billing.get("country"),
                "type": "contact",
            }]
        )
        return partner_id

    def _map_order_head(self, order, warehouse_id, lot_stock_id):
        currency = self.models.execute_kw(
            ODOO_DB, self.uid, self.odoo_pass,
            "res.currency", "search_read",
            [[("name", "=", order.get("currency", "HKD"))]],
            {"fields": ["id"], "limit": 1}
        )
        currency_id = currency[0]["id"] if currency else None
        partner_id = self._get_or_create_partner(order)

        order_head = safe_dict({
            "partner_id": partner_id,
            "client_order_ref": str(order.get("id")),
            "origin": safe_val(order.get("order_key")),
            "state": "draft",
            "currency_id": currency_id,
            "warehouse_id": warehouse_id,   # keep warehouse only
            "date_order": safe_datetime(order.get("date_created")),
            "validity_date": safe_datetime(order.get("date_completed")),
            "amount_total": safe_float(order.get("total")),
            "amount_tax": safe_float(order.get("total_tax")),
            "note": safe_val(order.get("customer_note")),
        })
        print('_map_woocommerce_order_head == ', order_head)
        return order_head

    def _map_order_lines(self, order):
        lines = []
        for line in order.get("line_items", []):
            sku = line.get("sku")
            product_id = None
            if sku:
                product_ids = self.models.execute_kw(
                    ODOO_DB, self.uid, self.odoo_pass,
                    "product.product", "search",
                    [[("default_code", "=", sku)]]
                )
                if product_ids:
                    product_id = product_ids[0]

            if not product_id:
                raise ValueError(f"SKU {sku} not found in Odoo. Sync products first!")

            lines.append({
                "product_id": product_id,
                "name": line.get("name"),
                "product_uom_qty": line.get("quantity"),
                "price_unit": safe_float(line.get("price")),
            })
        return lines

    def _get_models(self, odoo_user, odoo_pass):
        common = xmlrpc.client.ServerProxy(f"{ODOO_BASE_URL}/xmlrpc/2/common", allow_none=True)
        uid = common.authenticate(ODOO_DB, odoo_user, odoo_pass, {})
        if not uid:
            raise PermissionError("Failed authentication against Odoo.")
        models = xmlrpc.client.ServerProxy(f"{ODOO_BASE_URL}/xmlrpc/2/object", allow_none=True)
        return uid, models