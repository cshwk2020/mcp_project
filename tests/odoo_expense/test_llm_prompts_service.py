import pytest
from unittest.mock import MagicMock
from mcp_project.mcp_servers.mcp_llm_prompts.llm_extract_ocr import MCPLLMExtractOcrService
from mcp_project.mcp_servers.mcp_llm.deepseek_service import MCPDeepSeekService
from mcp_project.mcp_servers.mcp_odoo.odoo_expense_service import MCPOdooExpenseService
from mcp_project.config import MOCK_FILE_OCR_TEXTS
from mcp_project.mcp_shared.vault_util import VaultUtil

@pytest.fixture(scope="module")
def odoo_expense_service():
    return MCPOdooExpenseService()

@pytest.fixture(scope="module")
def deepseek_service():
    return MCPDeepSeekService()

@pytest.fixture(scope="module")
def ocr_extract_service(odoo_expense_service, deepseek_service):
    return MCPLLMExtractOcrService(odoo_expense_service, deepseek_service)


@pytest.mark.skip(reason="temporarily disabled")
def test_extract_info_from_ocr_text(ocr_extract_service):
    
    _vault = VaultUtil()
    odoo_user = _vault.get_odoo_user()
    odoo_pass = _vault.get_odoo_pass()
    results = ocr_extract_service.extract_info_from_ocr_text(
        odoo_user,
        odoo_pass,
        MOCK_FILE_OCR_TEXTS
    )

    print("results: ", results)
    

 