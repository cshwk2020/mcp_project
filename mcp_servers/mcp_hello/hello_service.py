# mcp_project/mcp_servers/mcp_hello/hello_service.py

class HelloWorldService:
    def __init__(self):
        self.service_name = "Hello World MCP Component"

    def get_tools_schema(self):
        """Your explicit, precise specifications for your tools"""
        return [{
            "name": "hello_get_greeting",
            "description": "Returns a test hello world greeting string.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The name to greet"}
                },
                "required": ["name"]
            }
        }, {
            "name": "hello_say_goodbye",
            "description": "Says goodbye to a user.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The name to goodbye"}
                }
            }
        }]

    # --- Target Methods ---
    # The method name exactly matches the suffix after "hello_"

    def get_greeting(self, name="World"):
        return {"result": f"Hello, {name}! This string comes directly from the method."}

    def say_goodbye(self, name="World"):
        return {"result": f"Goodbye, {name}!"}