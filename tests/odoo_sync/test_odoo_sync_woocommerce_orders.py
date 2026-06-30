import json
import pytest
from mcp_project.mcp_servers.mcp_api_sync.mcp_odoo_sync_woocommerce_service import MCPOdooSyncWoocommerceService
from mcp_project.mcp_servers.mcp_api_sync.mcp_xero_sync_po_service import MCPXeroSyncPurchaseOrderService
from mcp_project.mcp_shared.mcp_odoo_client import MCPOdooClient

@pytest.fixture(scope="module")
def odoo_client():
    return MCPOdooClient()

@pytest.fixture(scope="module")
def odoo_sync_woocommerce_service(odoo_client):
    return MCPOdooSyncWoocommerceService(odoo_client)


@pytest.mark.skip(reason="temporarily disabled")
def test_sync_woocommerce_orders_full_fields(odoo_sync_woocommerce_service):

    fake_orders = []
    with open("./test_data/woo_order.json") as f:
        fake_orders = json.load(f) 
        print("fake_orders==", fake_orders)

    result = odoo_sync_woocommerce_service.sync_woocommerce_orders_to_odoo(fake_orders, warehouse_code="whwoo")
    print("sync result:", result)

    assert result["status"] == "success"
    assert result["results"][0]["sale_order_id"] > 0
