import json
import pytest
from mcp_project.mcp_servers.mcp_api_sync.mcp_xero_sync_so_service import MCPXeroSyncSalesOrderService
from mcp_project.mcp_shared.mcp_odoo_client import MCPOdooClient
from mcp_project.xero_config import (
    load_xero_tokens, refresh_tokens, get_access_token,
    connectionAPI, xero_tenant_id, xero_tokens
)

@pytest.fixture(scope="module")
def odoo_client():
    return MCPOdooClient()

@pytest.fixture(scope="module")
def xero_so_service(odoo_client):
    return MCPXeroSyncSalesOrderService(odoo_client)

@pytest.mark.skip(reason="temporarily disabled")
def test_delete_all_sales_orders_in_xero(xero_so_service):
    global xero_tenant_id, xero_tokens
    
    # 1. Refresh OAuth2 tokens and resolve tenant configurations
    refresh_tokens()      
    xero_tokens = load_xero_tokens()   
    access_token = xero_tokens['access_token']             
    xero_tenant_id = connectionAPI()  

    # 2. Fire the batch deletion request targeting Quote documents (Sales Orders)
    print("\nRunning delete_all_preauth_sos cleanup routine...")
    deleted_preauth_sos = xero_so_service.delete_all_preauth_sos(access_token, xero_tenant_id)
    print(f"Deleted preauth SOs payload output: {deleted_preauth_sos}")

    # 3. Structural assertions
    assert isinstance(deleted_preauth_sos, list)
    if len(deleted_preauth_sos) > 0:
        # Verify that Xero successfully processed and set the records to DELETED
        assert deleted_preauth_sos[0]["Status"] == "DELETED"
        assert "QuoteID" in deleted_preauth_sos[0]
        print(f"Successfully flushed {len(deleted_preauth_sos)} Sales Orders out of Xero.")
 

    print("\nRunning delete_all_postauth_sos cleanup routine...")
    delete_all_postauth_sos = xero_so_service.delete_all_postauth_sos(access_token, xero_tenant_id)
    print(f"Deleted preauth SOs payload output: {delete_all_postauth_sos}")

    # 4. Structural assertions
    assert isinstance(delete_all_postauth_sos, list)
    if len(delete_all_postauth_sos) > 0:
        # Verify that Xero successfully processed and set the records to DELETED
        assert delete_all_postauth_sos[0]["Status"] == "DELETED"
        assert "QuoteID" in delete_all_postauth_sos[0]
        print(f"Successfully flushed {len(delete_all_postauth_sos)} Sales Orders out of Xero.")



@pytest.mark.skip(reason="temporarily disabled")
def test_pull_sales_orders_from_odoo(odoo_client):
    """
    Standalone test: pull sales orders from Odoo and verify structure.
    """
    sales_orders = odoo_client.get_sales_orders(limit=5)
    print("sales_orders==", sales_orders)

    assert isinstance(sales_orders, list)
    assert len(sales_orders) > 0
    assert "so_number" in sales_orders[0]
    assert "customer_name" in sales_orders[0]
    assert "line_items" in sales_orders[0]


 
def test_sync_all_sales_orders_to_xero(xero_so_service):
    global xero_tenant_id, xero_tokens
    refresh_tokens()      
    xero_tokens = load_xero_tokens()   
    access_token = xero_tokens['access_token']             
    xero_tenant_id = connectionAPI()  

    results = xero_so_service.sync_all_sales_orders(access_token, xero_tenant_id)
    print("sync SO results==", results)

    # Basic assertions: ensure API call returned data
    assert isinstance(results, list)
    if results and isinstance(results[0], dict):
        assert "Invoices" in results[0]



