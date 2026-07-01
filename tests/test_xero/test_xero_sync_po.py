import json
import pytest
from mcp_project.mcp_servers.mcp_api_sync.mcp_xero_sync_po_service import MCPXeroSyncPurchaseOrderService
from mcp_project.mcp_shared.mcp_odoo_client import MCPOdooClient
from mcp_project.xero_config import (
    load_xero_tokens, refresh_tokens, get_access_token,
    connectionAPI, xero_tenant_id, xero_tokens
)

@pytest.fixture(scope="module")
def odoo_client():
    return MCPOdooClient()

@pytest.fixture(scope="module")
def xero_po_service(odoo_client):
    return MCPXeroSyncPurchaseOrderService(odoo_client)



@pytest.mark.skip(reason="temporarily disabled")
def test_delete_all_bills_and_po_in_xero(xero_po_service):
    global xero_tenant_id, xero_tokens
    
    # Refresh tokens and gather configuration strings
    refresh_tokens()      
    xero_tokens = load_xero_tokens()   
    access_token = xero_tokens['access_token']             
    xero_tenant_id = connectionAPI()  

    # ─── STEP 1: CLEAN OUT BILLS FIRST ───────────────────────────────────
    # We must eliminate the bills first to break the back-reference locks
    print("\nRunning delete_all_bills routine...")
    voided_bills = xero_po_service.delete_all_bills(access_token, xero_tenant_id)
    print(f"Voided bills payload output: {voided_bills}")

    # Assertions for Bills Cleanup
    assert isinstance(voided_bills, list)
    if len(voided_bills) > 0:
        # Accepts AUTHORISED (if neutralized via Credit Notes), DELETED, or VOIDED
        assert voided_bills[0]["Status"] in ["AUTHORISED", "DELETED", "VOIDED"]
        assert voided_bills[0]["Type"] == "ACCPAY"

    # ─── STEP 2: CLEAN OUT THE PURCHASE ORDERS SECOND ────────────────────
    # Now that the bills are cleared, the PO states revert and allow deletion
    print("\nRunning delete_all_pos routine...")
    deleted_pos = xero_po_service.delete_all_pos(access_token, xero_tenant_id)
    print(f"Deleted POs payload output: {deleted_pos}")

    # Assertions for POs Cleanup
    assert isinstance(deleted_pos, list)
    if len(deleted_pos) > 0:
        # Check that the first updated PO returned is marked as DELETED
        assert deleted_pos[0]["Status"] == "DELETED"
        assert "PurchaseOrderID" in deleted_pos[0]



@pytest.mark.skip(reason="temporarily disabled")
def test_pull_purchase_orders_from_odoo(odoo_client):
    """
    Standalone test: pull purchase orders from Odoo and verify structure.
    """
    # Assumes get_purchase_orders setup exists in your MCPOdooClient wrapper
    purchase_orders = odoo_client.get_purchase_orders(limit=5)
    print("purchase_orders==", purchase_orders)

    assert isinstance(purchase_orders, list)
    assert len(purchase_orders) > 0
    assert "po_number" in purchase_orders[0]
    assert "vendor_name" in purchase_orders[0]
    assert "line_items" in purchase_orders[0]



def test_sync_all_purchase_orders_to_xero(xero_po_service):
    global xero_tenant_id, xero_tokens
    refresh_tokens()      
    xero_tokens = load_xero_tokens()   
    access_token = xero_tokens['access_token']             
    xero_tenant_id = connectionAPI()  

    results = xero_po_service.sync_all_purchase_orders(access_token, xero_tenant_id)
    print("sync PO results==", results)

    # Basic assertions: ensure API call returned something
    assert isinstance(results, list)
    if results and isinstance(results[0], dict):
        # Look for Purchase Orders structure key in response payload
        assert "PurchaseOrders" in results[0] or "PurchaseOrderNumber" in results[0]

 

