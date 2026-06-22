import asyncio
import hypercorn.asyncio
import hypercorn.config
from flask import Flask, request, jsonify, Response
import time, threading
import json

from mcp_project.mcp_servers.mcp_hello.hello_service import HelloWorldService
from mcp_project.mcp_servers.mcp_ocr.ocr_service import MCPOcrService 
from mcp_project.mcp_servers.mcp_llm.deepseek_service import MCPDeepSeekService 
from mcp_project.mcp_servers.mcp_odoo.odoo_expense_service import MCPOdooExpenseService
from mcp_project.mcp_servers.mcp_llm_prompts.llm_extract_ocr import MCPLLMExtractOcrService
from mcp_project.mcp_servers.mcp_api_sync.mcp_odoo_sync_service import MCPOdooSyncService 
from mcp_project.mcp_servers.mcp_api_sync.mcp_xero_sync_service import MCPXeroSyncService 


app = Flask(__name__)

class ServiceRegistry:
    def __init__(self):
        self.services = {}

    def register(self, prefix, service):
        self.services[prefix] = service

    def get_tools(self):
        all_tools = []
        for prefix, svc in self.services.items():
            for tool in svc.get_tools_schema():
                tool["name"] = f"{prefix}{tool['name']}"
                all_tools.append(tool)
        return all_tools

    def execute(self, tool_name, params):
        for prefix, svc in self.services.items():
            if tool_name.startswith(prefix):
                method_name = tool_name.replace(prefix, "")
                if hasattr(svc, method_name):
                    return getattr(svc, method_name)(**params)
                else:
                    raise ValueError(f"Method {method_name} not found in {svc}")
        raise ValueError(f"Tool {tool_name} not found")



#
_ocr_service = MCPOcrService()
_llm_service = MCPDeepSeekService()
_odoo_expense_service = MCPOdooExpenseService(_ocr_service)
_llm_prompt_ocr = MCPLLMExtractOcrService(_odoo_expense_service, _llm_service)
_api_sync_odoo = MCPOdooSyncService()
_api_sync_xero = MCPXeroSyncService()
#
registry = ServiceRegistry()
registry.register("hello_", HelloWorldService())
registry.register("ocr_", _ocr_service)
registry.register("llm_", _llm_service)
registry.register("odoo_expense_", _odoo_expense_service)
registry.register("llmprompt_", _llm_prompt_ocr)
registry.register("sync_odoo_", _api_sync_odoo)
registry.register("sync_xero_", _api_sync_xero)
# 
counter = {"i": 0}
#
def background_broadcast():
    while True:
        counter["i"] += 1
        time.sleep(2)

#
threading.Thread(target=background_broadcast, daemon=True).start()
#
@app.route("/subscribe")
def subscribe():
    def generate():
        while counter["i"] < 10:
            msg = {"event": "heartbeat", "msg": f"tick {counter['i']}"}
            yield f"data: {json.dumps(msg)}\n\n"
 
            time.sleep(2)
            print(f'looping...{counter["i"]}...')
        yield f"data: {json.dumps({'event':'done','msg':'stream finished'})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )


@app.route("/tools", methods=["GET"])
def get_tools():
    return jsonify({"tools": registry.get_tools()})

@app.route("/tools/<tool_name>", methods=["POST"])
def call_tool(tool_name):
    params = request.json or {}
    try:
        result = registry.execute(tool_name, params)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

######################################################
 


if __name__ == "__main__":
    print("Master MCP Routing Hub running on port 8000...")
    #app.run(port=8000, debug=True)

    config = hypercorn.config.Config()
    config.bind = ["0.0.0.0:8000"]

    asyncio.run(hypercorn.asyncio.serve(app, config))


