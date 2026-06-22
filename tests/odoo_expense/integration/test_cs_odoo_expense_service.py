import base64
import os
import asyncio
import pytest
import pytest_asyncio
from mcp_project.mcp_clients.mcp_client_main import QuartMCPClient
from mcp_project.mcp_shared.vault_util import VaultUtil
from mcp_project.config import MOCK_FILE_PATH, MOCK_FILE_OCR_TEXTS, MOCK_FILE_LLM_JSON


@pytest_asyncio.fixture(scope="module")
def event_loop():
    """Module-scoped event loop structure for integration testing lifecycle verification."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()



@pytest_asyncio.fixture(scope="module")
async def mcp_client(event_loop):
    """Initializes and connects down to the Flask master registry hub (port 8000)."""
    client = QuartMCPClient("http://127.0.0.1:8000")
    await client.connect()
    yield client
    if client.session and not client.session.closed:
        await client.session.close()


@pytest.mark.skip(reason="temporarily disabled")
@pytest.mark.asyncio(loop_scope="module")
async def test_fetch_dropdowns_integration(mcp_client):
    # 1. Get credentials from Vault
    _vault = VaultUtil()
    odoo_user = _vault.get_odoo_user()
    odoo_pass = _vault.get_odoo_pass()
    print("odoo_user: ", odoo_user)
    print("odoo_pass: ", odoo_pass)

    # 2. Call the registered tool over the network instead of the raw service method
    tool_name = "odoo_expense_fetch_dropdowns"
    response = await mcp_client.call_tool(
        tool_name, 
        {
            "odoo_user": odoo_user, 
            "odoo_pass": odoo_pass
        }
    )
    
    assert response is not None
    # Extract the dynamic inner payload from your client gateway framework mapping
    expense_dropdowns = response.get("result", response)
    print("expense_dropdowns: ", expense_dropdowns)

    # 如果有 error key → fail
    assert "error" not in expense_dropdowns, f"Odoo Expense error: {expense_dropdowns['error']}"

    # 如果有正常 categories/employee/manager → pass
    assert "categories" in expense_dropdowns
    assert "employee" in expense_dropdowns
    assert "manager" in expense_dropdowns

    return expense_dropdowns


@pytest.mark.skip(reason="temporarily disabled")
@pytest.mark.asyncio(loop_scope="module")
async def test_create_expense_integration(mcp_client):

    #  
    assert os.path.exists(MOCK_FILE_PATH), f"Target integration test receipt image not found: {MOCK_FILE_PATH}"

    # 
    _vault = VaultUtil()
    odoo_user = _vault.get_odoo_user()
    odoo_pass = _vault.get_odoo_pass()

    assert odoo_user is not None, "Vault connection failed to return valid odoo_user configuration string"
    assert odoo_pass is not None, "Vault connection failed to return valid odoo_pass configuration string"

    # 
    with open(MOCK_FILE_PATH, "rb") as f:
        mock_image_b64 = base64.b64encode(f.read()).decode("utf-8")

    mock_ocr_text = "\n".join(MOCK_FILE_OCR_TEXTS)
    mock_content_json = MOCK_FILE_LLM_JSON

    #  
    tool_name = "odoo_expense_create_expense"
    params = {
        "odoo_user": odoo_user,
        "odoo_pass": odoo_pass,
        "ocr_text": mock_ocr_text,
        "content_json": mock_content_json,
        "receipt_image_b64": mock_image_b64
    }

    #  
    response = await mcp_client.call_tool(tool_name, params)
    assert response is not None

    # 
    results = response.get("result", response)
    
    print("\n--- [Client Orchestrator Execution Pipeline Output] ---")
    print("results: ", results)
    print("-------------------------------------------------------\n")

    #  
    assert "error" not in results, f"Pipeline failed with script error trace: {results.get('error')}"
    assert results.get("status") == "success", f"Pipeline returned abnormal transaction target status: {results.get('status')}"
    
    #  
    assert "expense_id" in results, "Pipeline returned response without an active hr.expense primary key reference"
    assert "monitor_id" in results, "Pipeline returned response without an active automation.monitor reference"
    assert results.get("attachment_uploaded") is True, "Pipeline script bypassed or failed ir.attachment linking generation"

