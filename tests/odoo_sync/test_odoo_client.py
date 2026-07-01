# tests/test_odoo_client_delete.py
import pytest
from mcp_project.mcp_shared.mcp_odoo_client import MCPOdooClient

@pytest.fixture(scope="module")
def odoo_client():
    return MCPOdooClient()



def test_delete_all_sales_orders(odoo_client):
    result = odoo_client.delete_all_so()
    print("delete_all_so result:", result)
    assert result["status"] == "success"
    assert isinstance(result["deleted"], list)


def test_delete_all_purchase_orders(odoo_client):
    result = odoo_client.delete_all_po()
    print("delete_all_po result:", result)
    assert result["status"] == "success"
    assert isinstance(result["deleted"], list)
