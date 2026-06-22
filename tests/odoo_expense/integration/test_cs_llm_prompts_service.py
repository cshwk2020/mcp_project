import os
import pytest
import asyncio
import pytest_asyncio
from mcp_project.mcp_clients.mcp_client_main import QuartMCPClient
from mcp_project.config import MOCK_FILE_OCR_TEXTS
from mcp_project.mcp_shared.vault_util import VaultUtil

@pytest_asyncio.fixture(scope="module")
def event_loop():
    """Manages the shared module-level async event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def mcp_client(event_loop):
    """Spins up your real client and establishes an active HTTP/SSE connection"""
    client = QuartMCPClient("http://localhost:8000")
    await client.connect()
    yield client
    if client.session and not client.session.closed:
        await client.session.close()


@pytest.mark.skip(reason="temporarily disabled")
@pytest.mark.asyncio(loop_scope="module")
async def test_mcp_client_llm_extract_ocr(mcp_client):
    """
    Integration Test: Fires an async network payload from QuartMCPClient to the 
    master server routing engine, validating the cross-service Odoo + DeepSeek pipeline.
    """
    # 1. Fetch parameters from live Vault storage
    _vault = VaultUtil()
    odoo_user = _vault.get_odoo_user()
    odoo_pass = _vault.get_odoo_pass()
    
    assert odoo_user is not None, "Vault odoo_user parameter is empty"
    assert odoo_pass is not None, "Vault odoo_pass parameter is empty"
    assert len(MOCK_FILE_OCR_TEXTS) > 0, "MOCK_FILE_OCR_TEXTS list config is empty"

    # 2. Build the exact payload schema structure expected by the service
    tool_name = "llmprompt_extract_info_from_ocr_text"
    params = {
        "odoo_user": odoo_user,
        "odoo_pass": odoo_pass,
        "ocr_texts": MOCK_FILE_OCR_TEXTS
    }

    #  
    result = await mcp_client.call_tool(tool_name, params)

    print("real result: ", result)


    assert result is not None
    assert "error" not in result, f"Server returned error message: {result.get('error')}"

    # 
    data_payload = result.get("result", result)
    print("\n[LLM OCR Extract Pipeline Integration Success]:", data_payload)
    
    #  
    assert isinstance(data_payload, dict), f"Expected structural dict from LLM, got {type(data_payload)}"
 