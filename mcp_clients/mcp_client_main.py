# mcp_project/mcp_clients/buddy1/client_quart.py
import asyncio
import hypercorn.asyncio
import hypercorn.config
from quart import Quart, request, jsonify
from quart_cors import cors
from mcp_project.mcp_clients.mcp_client import MCPClient
from mcp_project.mcp_clients.hello_client.hello_client_routes import HelloMCPClientRoutes
from mcp_project.mcp_clients.odoo_expense.expense_client_routes import ExpenseMCPClientRoutes
from mcp_project.mcp_clients.odoo_expense.langgraph_pipeline_expense import create_expense_graph


class QuartMCPClient(MCPClient):

    def __init__(self, server_url: str):
        super().__init__(server_url)
        self.app = Quart(__name__)
        self.app = cors(self.app, allow_origin="*")

        @self.app.before_request
        async def ensure_client():
            if self.session is None:
                await self.connect()

        # Core Protocol Routes (Kept generic for all tools)
        @self.app.route("/get_tools", methods=["GET"])
        async def api_get_tools():
            try:
                tools_data = await self.get_tools()
                return jsonify({"status": "success", "data": tools_data})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route("/call_tool/<tool_name>", methods=["POST"])
        async def api_call_tool(tool_name):
            params = await request.get_json() or {}
            try:
                result = await self.call_tool(tool_name, params)
                return jsonify({"status": "success", "tool": tool_name, "result": result})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

    def run(self, port=5000):
        self.app.run(port=port, debug=True)


if __name__ == "__main__":
    # 1. Start the core platform client targeting port 8000
    client = QuartMCPClient("http://localhost:8000")
    
    # 2. Inject your isolated hello feature routes into it
    HelloMCPClientRoutes(app=client.app, mcp_client=client)
    #
    langgraph_pipeline = create_expense_graph()
    print("DEBUG pipeline methods:", dir(langgraph_pipeline))

    ExpenseMCPClientRoutes(app=client.app, mcp_client=client, langgraph_pipeline=langgraph_pipeline)

    # 3. Fire up the user-facing app
    # client.run(port=5000)

    config = hypercorn.config.Config()
    config.bind = ["0.0.0.0:5000"]

    asyncio.run(hypercorn.asyncio.serve(client.app, config))



