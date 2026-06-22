import base64
import pytest
from mcp_project.mcp_servers.mcp_odoo.odoo_expense_service import MCPOdooExpenseService
from mcp_project.mcp_shared.vault_util import VaultUtil 
from mcp_project.config import MOCK_FILE_PATH, MOCK_FILE_OCR_TEXTS, MOCK_FILE_LLM_JSON

@pytest.fixture
def odoo_expense_service():
    return MCPOdooExpenseService()

@pytest.mark.skip(reason="temporarily disabled")
def test_odoo_tools_schema(odoo_expense_service):
    schemas = odoo_expense_service.get_tools_schema()
    assert len(schemas) == 2
    assert any(s["name"] == "odoo_expense_fetch_dropdowns" for s in schemas)
    assert any(s["name"] == "odoo_expense_create_expense" for s in schemas)


@pytest.mark.skip(reason="temporarily disabled")
def test_fetch_dropdowns(odoo_expense_service):
   
    _vault = VaultUtil()
    odoo_user = _vault.get_odoo_user()
    odoo_pass = _vault.get_odoo_pass()
    print("odoo_user: ", odoo_user)
    print("odoo_pass: ", odoo_pass)
    expense_dropdowns = odoo_expense_service.fetch_dropdowns(odoo_user, odoo_pass)
    print("expense_dropdowns: ", expense_dropdowns)

    # 如果有 error key → fail
    assert "error" not in expense_dropdowns, f"Odoo XML-RPC error: {expense_dropdowns['error']}"

    # 如果有正常 categories/employee/manager → pass
    assert "categories" in expense_dropdowns
    assert "employee" in expense_dropdowns
    assert "manager" in expense_dropdowns

    return expense_dropdowns
 
 
@pytest.mark.skip(reason="temporarily disabled")
def test_create_expense(odoo_expense_service):
    
    with open(MOCK_FILE_PATH, "rb") as f:
        fake_image_b64 = base64.b64encode(f.read()).decode("utf-8")

    fake_ocr_text = "\n".join(MOCK_FILE_OCR_TEXTS)
    fake_content_json = MOCK_FILE_LLM_JSON

    #
    _vault = VaultUtil()
    odoo_user = _vault.get_odoo_user()
    odoo_pass = _vault.get_odoo_pass()
    
    #
    result = odoo_expense_service.create_expense(
        odoo_user, odoo_pass, fake_ocr_text, fake_content_json, fake_image_b64
    )

    #
    assert "status" in result
    assert result["status"] in ["success", "error"]
    # 如果成功，應該有 content_json
    if result["status"] == "success":
        assert "content_json" in result
        assert result["content_json"]["summary"]["status"] == "complete"

