import os
import pytest
import asyncio
import base64
import pytest_asyncio
from mcp_project.mcp_clients.mcp_client_main import QuartMCPClient

TEST_FILE_PATH = "/Users/cshwk1995/Desktop/img/receipts/IMG_2150.jpg"

@pytest_asyncio.fixture(scope="module")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def mcp_client(event_loop):
    client = QuartMCPClient("http://localhost:8000")
    await client.connect()
    yield client
    if client.session and not client.session.closed:
        await client.session.close()


@pytest.mark.skip(reason="temporarily disabled")
@pytest.mark.asyncio(loop_scope="module")
async def test_mcp_client_call_run_file(mcp_client):
    
    assert os.path.exists(TEST_FILE_PATH)
    
    tool_name = "ocr_run_file_b64" 
    params = {"filepath": TEST_FILE_PATH} 
    
    result = await mcp_client.call_tool(tool_name, params)
    
    assert result is not None
    assert "error" not in result, f"Server returned error: {result.get('error')}"
    
    data_payload = result.get("result", result)
    assert "texts" in data_payload
    assert "image_base64" in data_payload
    print("\n[Run File Integration Success]:", data_payload["texts"])


@pytest.mark.skip(reason="temporarily disabled")
@pytest.mark.asyncio(loop_scope="module")
async def test_mcp_client_call_run_bytes(mcp_client):

    assert os.path.exists(TEST_FILE_PATH)
    
    with open(TEST_FILE_PATH, "rb") as f:
        encoded_string = base64.b64encode(f.read()).decode('utf-8')
        
    tool_name = "ocr_run_bytes_b64" 
    params = {
        "image_bytes": encoded_string 
    }
    
    result = await mcp_client.call_tool(tool_name, params)
    
    assert result is not None
    assert "error" not in result, f"Server returned error: {result.get('error')}"
    
    data_payload = result.get("result", result)
    assert "texts" in data_payload
    assert "image_base64" in data_payload
    print("\n[Run Bytes Integration Success]:", data_payload["texts"])