import os
import pytest
from mcp_project.mcp_servers.mcp_llm.deepseek_service import MCPDeepSeekService
from mcp_project.mcp_servers.mcp_odoo.odoo_expense_service import MCPOdooExpenseService
from test_odoo_expense_service import test_fetch_dropdowns
from mcp_project.mcp_prompt_templates.prompt_template_ocr import build_ocr_prompt_messages
from mcp_project.config import MODE_REAL, MOCK_FILE_OCR_TEXTS, MOCK_FILE_LLM_JSON

@pytest.fixture
def deepseek_service():
    return MCPDeepSeekService()

@pytest.fixture
def odoo_expense_service():
    return MCPOdooExpenseService()

def test_deepseek_tools_schema(deepseek_service):
    schemas = deepseek_service.get_tools_schema()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "deepseek_prompt_query"
    assert "messages" in schemas[0]["input_schema"]["properties"]


@pytest.mark.skip(reason="temporarily disabled")
def test_llm_extract_ocr(odoo_expense_service, deepseek_service):
 
    if MODE_REAL == False:
        return MOCK_FILE_LLM_JSON

    else:
        expense_dropdowns = test_fetch_dropdowns(odoo_expense_service)
        print('expense_dropdowns: ', expense_dropdowns)

        _categories = expense_dropdowns["categories"]
        _employee = expense_dropdowns["employee"]
        _manager = expense_dropdowns["manager"]
        
        ocr_text = "\n".join(MOCK_FILE_OCR_TEXTS)
        employee_name = _employee["name"]
        manager_name = _manager["name"]
        categories_str = ", ".join([c["name"] for c in _categories])

        print('employee_name: ', employee_name)
        print('employee_name: ', employee_name)
        print('categories_str: ', categories_str)

        prompt_messages = build_ocr_prompt_messages(ocr_text, employee_name, manager_name, categories_str)
        print("prompt_messages: ", prompt_messages)
        results = deepseek_service.prompt_query(prompt_messages)
        print('results: ', results)

