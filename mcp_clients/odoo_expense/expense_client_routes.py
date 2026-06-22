import uuid
import json
import base64
from quart import request, Response, jsonify, websocket
from quart_cors import cors
from mcp_project.mcp_shared.debug_log_queue import DEBUG_LOG_QUEUE

PENDING_EXPENSE_ASSETS = {}

class ExpenseMCPClientRoutes:
    
    def __init__(self, app, mcp_client, langgraph_pipeline):
        self.app = app
        self.mcp_client = mcp_client
        self.pipeline = langgraph_pipeline
        self.register_routes()

    def register_routes(self):

        # for React UI RHS sequential debug log stream
        @self.app.websocket("/ws/debuglog")
        async def ws_debuglog():
            while True:
                # 等待有 log 入 queue
                log = await DEBUG_LOG_QUEUE.get()
                # 推送到 WebSocket client
                await websocket.send(json.dumps(log))

 
        @self.app.route("/api/expense/upload", methods=["POST"])
        async def handle_expense_upload():
            form_files = await request.files
            uploaded_file = form_files.get("receipt")
            if not uploaded_file:
                return jsonify({"status": "error", "message": "No valid receipt asset provided."}), 400

            session_id = str(uuid.uuid4())
            raw_bytes = uploaded_file.read()
            b64_str = base64.b64encode(raw_bytes).decode("utf-8")
            PENDING_EXPENSE_ASSETS[session_id] = b64_str

            print(f"[PHASE 1 SUCCESS]: Handshake locked for ID: {session_id}. Awaiting stream.")
            return jsonify({"status": "accepted", "sessionId": session_id})


        # for React UI LHS state diagram update
        @self.app.route("/api/expense/stream/<session_id>", methods=["GET"])
        async def stream_expense_pipeline(session_id):
            image_b64 = PENDING_EXPENSE_ASSETS.pop(session_id, "")

            async def event_generator():
                initial_state = {
                    "session_id": session_id,
                    "image_b64": image_b64,
                    "ocr_text": "",
                    "content_json": {},
                    "final_response": {},
                    "mcp_client": self.mcp_client,
                    "error": ""
                }
                config = {"configurable": {"thread_id": session_id}}

                try:
                    async for chunk in self.pipeline.astream(initial_state, config=config):
                        for node_name, state_update in chunk.items():
                            if node_name == "__start__":
                                continue
                            if not state_update:
                                state_update = {"info": f"{node_name} returned no update"}
                            payload = {
                                "status": "IN_PROGRESS",
                                "node_executed": node_name,
                                "updated_state_delta": state_update
                            }
                            yield f"data: {json.dumps(payload)}\n\n"
                    yield f"data: {json.dumps({'status': 'COMPLETE'})}\n\n"
                except Exception as pipeline_err:
                    error_payload = {
                        "status": "COMPLETE",
                        "node_executed": "pipeline_error",
                        "updated_state_delta": {"error": str(pipeline_err)}
                    }
                    yield f"data: {json.dumps(error_payload)}\n\n"

            return Response(event_generator(), content_type="text/event-stream")
