import json
import pytest
from mcp_project.mcp_servers.mcp_api_sync.mcp_xero_sync_item_service import MCPXeroSyncItemService
from mcp_project.mcp_shared.mcp_odoo_client import MCPOdooClient
from mcp_project.xero_config import (
    load_xero_tokens, refresh_tokens, get_access_token,
    connectionAPI, xero_tenant_id, xero_tokens, 
    XERO_INVOICES_URL, XERO_MANUAL_JOURNAL_URL
)

@pytest.fixture(scope="module")
def odoo_client():
    return MCPOdooClient()

@pytest.fixture(scope="module")
def xero_item_service(odoo_client):
    return MCPXeroSyncItemService(odoo_client)


@pytest.mark.skip(reason="temporarily disabled")
def test_pull_products_from_odoo(odoo_client):
    """
    Standalone test: pull products from Odoo and verify structure.
    """
    products = odoo_client.get_products(limit=5)
    print("products==", products)

    assert isinstance(products, list)
    assert len(products) > 0
    assert "code" in products[0]
    assert "name" in products[0]


@pytest.mark.skip(reason="temporarily disabled")
def test_sync_all_products_to_xero(xero_item_service):

    global xero_tenant_id, xero_tokens
    refresh_tokens()      
    xero_tokens = load_xero_tokens()   
    access_token = xero_tokens['access_token']             
    xero_tenant_id = connectionAPI()  


    results = xero_item_service.sync_all_items(access_token, xero_tenant_id)
    print("sync results==", results)

    # Basic assertions: ensure API call returned something
    assert isinstance(results, list)
    # If Xero API is mocked, check payload structure
    if results and isinstance(results[0], dict):
        assert "Code" in results[0].get("Items", [{}])[0] or "Code" in results[0]
