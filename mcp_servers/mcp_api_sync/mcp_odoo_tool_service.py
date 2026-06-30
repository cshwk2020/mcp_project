import logging
from mcp_project.mcp_shared.vault_util import VaultUtil
from mcp_project.config import ODOO_BASE_URL, ODOO_DB

logger = logging.getLogger(__name__)

class MCPOdooToolService:
    def __init__(self, odoo_client):
        self.service_name = "Odoo Tool MCP Server"
        self.odoo_client = odoo_client
        _vault = VaultUtil()
        self.odoo_user = _vault.get_odoo_user()
        self.odoo_pass = _vault.get_odoo_pass()
        self.uid, self.models = self._get_models(self.odoo_user, self.odoo_pass)

    def get_tools_schema(self):
        return [
            {
                "name": "delete_all_purchase_orders",
                "description": "Cancel and delete all Purchase Orders in Odoo.",
                "input_schema": {"type": "object", "properties": {}}
            },
            {
                "name": "delete_all_sale_orders",
                "description": "Cancel and delete all Sale Orders in Odoo.",
                "input_schema": {"type": "object", "properties": {}}
            }
        ]

    def delete_all_purchase_orders(self):
        try:
            result = self.odoo_client.delete_all_po()
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"delete_all_purchase_orders failed: {str(e)}")
            return {"error": str(e)}

    def delete_all_sale_orders(self):
        try:
            result = self.odoo_client.delete_all_so()
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"delete_all_sale_orders failed: {str(e)}")
            return {"error": str(e)}

    def _get_models(self, odoo_user, odoo_pass):
        import xmlrpc.client
        common = xmlrpc.client.ServerProxy(f"{ODOO_BASE_URL}/xmlrpc/2/common", allow_none=True)
        uid = common.authenticate(ODOO_DB, odoo_user, odoo_pass, {})
        if not uid:
            raise PermissionError("Failed authentication against Odoo.")
        models = xmlrpc.client.ServerProxy(f"{ODOO_BASE_URL}/xmlrpc/2/object", allow_none=True)
        return uid, models
