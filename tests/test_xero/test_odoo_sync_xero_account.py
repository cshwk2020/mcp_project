import pytest
import json
from mcp_project.mcp_servers.mcp_api_sync.mcp_xero_sync_service import MCPXeroSyncService


@pytest.fixture(scope="module")
def xero_sync_service():
    return MCPXeroSyncService()


@pytest.mark.skip(reason="temporarily disabled")
def test_sync_sale_orders_and_pickings(xero_sync_service):
    result = xero_sync_service.sync_sale_orders_and_pickings()

    print("\n==============\n")
    print(json.dumps(result, default=str, indent=2))
    print("\n==============\n")

    # 基本結構檢查
    assert result["status"] == "success"
    assert "sale_orders" in result
    assert "pickings" in result
    assert isinstance(result["sale_orders"], list)
    assert isinstance(result["pickings"], list)

    # 如果有數據 → 檢查 Reference pair
    if result["sale_orders"] and result["pickings"]:
        so_ref = result["sale_orders"][0]["Invoices"][0]["Reference"]
        pk_ref = result["pickings"][0]["ManualJournals"][0]["Reference"]
        assert so_ref == pk_ref, f"Reference mismatch: {so_ref} vs {pk_ref}"
    else:
        pytest.skip("No outstanding sale orders/pickings to sync")


@pytest.mark.skip(reason="temporarily disabled")
def test_pull_sale_orders_to_xero(xero_sync_service):
    """
    測試從 Odoo 拉出 sale.order outstanding records，
    並且 prepare JSON payload for Xero Invoice API。
    """
    result = xero_sync_service.pull_sale_orders_to_xero()
 
    print("\n==============\n")
    print(json.dumps(result, default=str))
    print("\n==============\n")

    assert result["status"] == "success"
    assert "payloads" in result
    assert isinstance(result["payloads"], list)
    if result["payloads"]:
        invoice = result["payloads"][0]["Invoices"][0]
        assert "InvoiceNumber" in invoice
        assert "LineItems" in invoice
        assert invoice["Type"] == "ACCREC"


@pytest.mark.skip(reason="temporarily disabled")
def test_pull_stock_pickings_to_xero(xero_sync_service):
    """
    測試從 Odoo 拉出 stock.picking outstanding records，
    並且 prepare JSON payload for Xero Manual Journal API (COGS)。
    """
    result = xero_sync_service.pull_stock_pickings_to_xero()
    
    print("\n==============\n")
    print(json.dumps(result, default=str))
    print("\n==============\n")

    assert result["status"] == "success"
    assert "payloads" in result
    assert isinstance(result["payloads"], list)

    if result["payloads"]:
        journal = result["payloads"][0]["ManualJournals"][0]
        assert "Reference" in journal
        assert "JournalLines" in journal
        assert journal["Status"] in ["POSTED", "DRAFT"]

