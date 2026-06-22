# mcp_project/mcp_clients/buddy1/hello_client_routes.py
from quart import Quart, request, jsonify

class HelloMCPClientRoutes:
    
    def __init__(self, app: Quart, mcp_client):
        self.app = app
        self.mcp = mcp_client
        
        # Register the routes dynamically onto the passed app
        self._register_routes()

    def _register_routes(self):
        

 
        @self.app.route("/test_hello", methods=["GET"])
        async def api_test_hello():
            test_params = {"name": request.args.get("name", "Buddy")}
            try:
                # Call using the shared client session instance
                result = await self.mcp.call_tool("hello_get_greeting", test_params)
                return jsonify({
                    "status": "success",
                    "message": "Connected seamlessly!",
                    "server_response": result
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route("/test_goodbye", methods=["GET"])
        async def api_test_goodbye():
            test_params = {"name": request.args.get("name", "Buddy")}
            try:
                result = await self.mcp.call_tool("hello_say_goodbye", test_params)
                return jsonify({
                    "status": "success",
                    "message": "Connected seamlessly!",
                    "server_response": result
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500