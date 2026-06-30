import logging
from mcp_project.mcp_shared.safe_utils import safe_dict, safe_datetime, safe_val, safe_float

logger = logging.getLogger(__name__)

class MCPOdooSyncShoplifyService:
    def __init__(self, odoo_client):
        self.service_name = "Odoo Sync Shoplify MCP Server"
        self.odoo_client = odoo_client

    def get_tools_schema(self):
        return [
            {
                "name": "sync_shoplify_orders_to_odoo",
                "description": "Manual sync Shopify orders into Odoo (Invoice + Inventory).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "orders": {"type": "array"},
                        "warehouse": {"type": "string", "default": "shopify_wh"}
                    },
                    "required": ["orders"]
                }
            }
        ]

    def sync_shoplify_orders_to_odoo(self, orders, warehouse_code="whsho"):
        warehouse_id, lot_stock_id, delivery_type_id = self.odoo_client.get_warehouse_context(warehouse_code)
        return self._sync_pipeline(
            orders,
            warehouse_id,
            lot_stock_id,
            delivery_type_id,
            source="shopify",
            map_head=lambda o, wid, lid, did: self._map_order_head(o, wid, lid, did),
            map_lines=self._map_order_lines
        )

    def _sync_pipeline(self, orders, warehouse_id, lot_stock_id, delivery_type_id, source, map_head, map_lines):
        try:
            results = []
            for order in orders:
                order_status = order.get("financial_status")
                if order_status not in ("paid", "refunded"):
                    continue

                # revoke old order
                self.odoo_client.revoke_order(str(order.get("id")), delivery_type_id)

                order_head = map_head(order, warehouse_id, lot_stock_id, delivery_type_id)
                order_lines = map_lines(order)

                sale_order_id = self.odoo_client.create_order(order_head, order_lines, delivery_type_id)

                results.append({
                    "order_id": order.get("id"),
                    "sale_order_id": sale_order_id,
                    "status": "success"
                })

            return {"status": "success", "results": results}
        except Exception as e:
            logger.error(f"{source} sync failed: {str(e)}")
            return {"error": str(e)}

    def _map_order_head(self, order, warehouse_id, lot_stock_id, delivery_type_id):
        shop_cur = order.get("currency", "USD")
        company_cur = self.odoo_client.get_company_currency()
        currency_id = self.odoo_client.get_currency_id(company_cur)
        partner_id = self.odoo_client.get_or_create_partner(order)

        total_price_converted = self.odoo_client.convert_currency(order.get("total_price"), shop_cur, company_cur)
        total_tax_converted = self.odoo_client.convert_currency(order.get("total_tax"), shop_cur, company_cur)

        return safe_dict({
            "partner_id": partner_id,
            "client_order_ref": str(order.get("id")),
            "origin": safe_val(order.get("confirmation_number")),
            "state": "draft",
            "currency_id": currency_id,
            "warehouse_id": warehouse_id,
            "date_order": safe_datetime(order.get("created_at")),
            "validity_date": safe_datetime(order.get("processed_at")),
            "amount_total": total_price_converted,
            "amount_tax": total_tax_converted,
            "note": safe_val(order.get("note")),
        })

    def _map_order_lines(self, order):
        shop_cur = order.get("currency", "USD")
        company_cur = self.odoo_client.get_company_currency()

        lines = []
        for line in order.get("line_items", []):
            product_id = self.odoo_client.find_product_by_sku(line.get("sku"))
            if not product_id:
                raise ValueError(f"SKU {line.get('sku')} not found in Odoo. Sync products first!")

            price_unit_converted = self.odoo_client.convert_currency(line.get("price"), shop_cur, company_cur)

            lines.append({
                "product_id": product_id,
                "name": line.get("title"),
                "product_uom_qty": line.get("quantity"),
                "price_unit": price_unit_converted,
            })
        return lines
