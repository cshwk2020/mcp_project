import logging
from mcp_project.mcp_prompt_templates.prompt_template_ocr import build_ocr_prompt_messages
from mcp_project.config import MODE_OCR_EXCEPTION, MODE_LLM_PARSE_OCR_EXCEPTION, MODE_REAL, MOCK_FILE_OCR_TEXTS, MOCK_FILE_LLM_JSON

logger = logging.getLogger(__name__)

class MCPLLMExtractOcrService:

    def __init__(self, odoo_service, deepseek_service):
        self.service_name = "LLM Extraction OCR Service"
        # Inject structural system dependencies 
        self.odoo_service = odoo_service
        self.deepseek_service = deepseek_service

    def get_tools_schema(self):
        return [{
            "name": "llmprompt_extract_info_from_ocr_text",
            "description": "extract information from OCR text by LLM.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "odoo_user": {"type": "string"},
                    "odoo_pass": {"type": "string"},
                    "ocr_texts": {
                        "type": "array", 
                        "items": {"type": "string"}, 
                        "description": "Raw string list extracted via OCR"
                    }
                },
                "required": ["odoo_user", "odoo_pass", "ocr_texts"]
            }
        }]

    def extract_info_from_ocr_text(self, odoo_user, odoo_pass, ocr_texts):

        if MODE_LLM_PARSE_OCR_EXCEPTION == True:
            raise ValueError("MODE_LLM_PARSE_OCR_EXCEPTION")

        if MODE_REAL == False:
            return MOCK_FILE_LLM_JSON

        else:
            expense_dropdowns = self.odoo_service.fetch_dropdowns(odoo_user, odoo_pass)
            if "error" in expense_dropdowns:
                return {"error": f"Failed compiling Odoo context framework: {expense_dropdowns['error']}"}

            _categories = expense_dropdowns.get("categories", [])
            _employee = expense_dropdowns.get("employee", {})
            _manager = expense_dropdowns.get("manager", {})

            # 
            ocr_string = "\n".join(ocr_texts)
            employee_name = _employee.get("name", "Unknown Employee")
            manager_name = _manager.get("name", "Unknown Manager")
            categories_str = ", ".join([c.get("name", "") for c in _categories if c.get("name")])

            #  
            prompt_messages = build_ocr_prompt_messages(
                ocr_string, 
                employee_name, 
                manager_name, 
                categories_str
            )

            #   
            results = self.deepseek_service.prompt_query(prompt_messages)
            return results
            
