import json
import pytest
from mcp_project.mcp_servers.mcp_api_sync.mcp_odoo_sync_shoplify_service import MCPOdooSyncShoplifyService
from mcp_project.mcp_servers.mcp_api_sync.mcp_xero_sync_po_service import MCPXeroSyncPurchaseOrderService
from mcp_project.mcp_shared.mcp_odoo_client import MCPOdooClient

@pytest.fixture(scope="module")
def odoo_client():
    return MCPOdooClient()

@pytest.fixture(scope="module")
def odoo_sync_shoplify_service(odoo_client):
    return MCPOdooSyncShoplifyService(odoo_client)

@pytest.mark.skip(reason="temporarily disabled")
def test_sync_shoplify_orders_full_fields(odoo_sync_shoplify_service):
    with open("./test_data/shopify_order.json") as f:
        data = json.load(f)
        fake_orders = data.get("orders", [])

    result = odoo_sync_shoplify_service.sync_shoplify_orders_to_odoo(fake_orders, warehouse_code="whsho")
    print("Shopify sync result:", result)

    assert result["status"] == "success"
    assert result["results"][0]["sale_order_id"] > 0
