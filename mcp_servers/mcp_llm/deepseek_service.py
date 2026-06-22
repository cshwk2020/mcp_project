import requests, json
from mcp_project.config import LLM_API_MODEL_VER, LLM_API_KEY, LLM_API_URL  
from mcp_project.config import MOCK_FILE_LLM_JSON

class MCPDeepSeekService:
    def __init__(self):
        self.service_name = "DeepSeek MCP Component"
        self.api_key = LLM_API_KEY
        self.api_model = LLM_API_MODEL_VER
        self.url = LLM_API_URL

    def get_tools_schema(self):
        return [{
            "name": "deepseek_prompt_query",
            "description": "Send a messages list to DeepSeek API and return structured JSON.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "messages": {"type": "array", "description": "List of role/content dicts"}
                },
                "required": ["messages"]
            }
        }]

    def create_payload(self, message_list):
        """Wrap messages list into DeepSeek payload"""
        return {
            "model": self.api_model,
            "messages": message_list,
            "response_format": {"type": "json_object"},
            "reasoning_effort": "low",
            "stream": False
        }

    def prompt_query(self, message_list):
        payload = self.create_payload(message_list)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        response = requests.post(self.url, headers=headers, json=payload)
        raw = response.json()
        content_str = raw["choices"][0]["message"]["content"]

        return json.loads(content_str)
        