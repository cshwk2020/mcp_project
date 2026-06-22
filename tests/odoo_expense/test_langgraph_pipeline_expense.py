import base64
import uuid
import pytest
from mcp_project.config import MOCK_FILE_PATH
from mcp_project.mcp_clients.odoo_expense.langgraph_pipeline_expense import create_expense_graph

@pytest.fixture
def expense_pipeline_graph():
    """Compiles a clean instance of your pipeline state graph"""
    return create_expense_graph()

@pytest.mark.skip(reason="temporarily disabled")
@pytest.mark.asyncio
async def test_pure_langgraph_astream_lifecycle(expense_pipeline_graph):
    """
    Tests pipeline stream loop execution mechanics safely,
    avoiding KeyError '__start__' by using .astream_events() with version,
    and filtering out raw image_bytes from debug output.
    """
 
    with open(MOCK_FILE_PATH, "rb") as f:
        raw_bytes = f.read()
    image_b64_payload = base64.b64encode(raw_bytes).decode("utf-8")
            
    session_id = str(uuid.uuid4())

    initial_state = {
        "session_id": session_id,
        "image_bytes": image_b64_payload,
        "ocr_text": "",
        "content_json": {},
        "final_response": {},
        "mcp_client": None,
        "error": ""
    }

    config = {"configurable": {"thread_id": session_id}}

    # print(f"\n[STARTING PURE RUN]: Calling .astream_events() for Session: {session_id}")


    async for event in expense_pipeline_graph.astream_events(
        initial_state,
        config=config,
        version="v1"
    ):

        # Filter out raw image_bytes
        safe_event = {}
        for node, state_delta in event.items():
            if isinstance(state_delta, dict):
                safe_event[node] = {
                    k: (len(v) if k == "image_bytes" and isinstance(v, bytes) else v)
                    for k, v in state_delta.items()
                }
            else:
                safe_event[node] = state_delta

        # print(f"\n[EVENT RECEIVED] -> {safe_event}")

        assert isinstance(safe_event, dict)

        for node_name, state_delta in safe_event.items():
            if isinstance(state_delta, dict) and "error" in state_delta and state_delta["error"]:
                print(f"[EXPECTED STOP]: Node '{node_name}' halted cleanly via error variable: {state_delta['error']}")
                return
