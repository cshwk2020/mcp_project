import os
import io
import cv2
import xmlrpc.client
import base64
import logging
from datetime import datetime
#
from mcp_project.mcp_shared.vault_util import VaultUtil
from mcp_project.mcp_shared.image_util import convert_b64_to_bytes_and_gray
from mcp_project.config import ODOO_BASE_URL, ODOO_DB
from mcp_project.config import UPLOAD_FOLDER 
from mcp_project.config import MODE_LLM_CREATE_ODOO_EXPENSE_EXCEPTION

from mcp_project.mcp_shared.logging_util import logger
logger = logging.getLogger(__name__)

class MCPOdooExpenseService:
    def __init__(self, _ocr_service=None):
        self.service_name = "Odoo Expense MCP Component"
        #  
        _vault = VaultUtil()
        self.odoo_user = _vault.get_odoo_user()
        self.odoo_pass = _vault.get_odoo_pass()
        #
        self.ocr_service = _ocr_service


    def get_tools_schema(self):
        """Exposes standard structural contracts to your central Flask Registry."""
        return [
            {
                "name": "odoo_expense_fetch_dropdowns",
                "description": "Fetch categories, employee data, and manager relationships from Odoo.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "odoo_user": {"type": "string"},
                        "odoo_pass": {"type": "string"}
                    },
                    "required": ["odoo_user", "odoo_pass"]
                }
            },
            {
                "name": "odoo_expense_create_expense",
                "description": "Orchestrates full OCR extraction, structural LLM processing, and inserts records into Odoo using create_with_monitor.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "odoo_user": {"type": "string"},
                        "odoo_pass": {"type": "string"},
                        "ocr_text": {"type": "string", "description": "Raw text lines extracted via OCR engine"},
                        "content_json": {
                            "type": "object", 
                            "description": "JSON dict matching {'summary': {...}, 'details': [...]}"
                        },
                        "receipt_image_b64": {"type": "string", "description": "Base64 encoded raw image file string"}
                    },
                    "required": ["odoo_user", "odoo_pass", "ocr_text", "content_json", "receipt_image_b64"]
                }
            }
        ]


    # 
    def fetch_dropdowns(self, odoo_user, odoo_pass):
        """Wrapper endpoint executing runtime Odoo context exploration."""
        try:
            uid, models = self._get_models(odoo_user, odoo_pass)
            
            # 1. Fetch products available for expenses
            categories = models.execute_kw(
                ODOO_DB, uid, odoo_pass,
                "product.product", "search_read",
                [[["can_be_expensed", "=", True]]],
                {"fields": ['id', 'name', 'default_code']}
            )

            # 2. Extract employee assigned to the credentials user
            employees = models.execute_kw(
                ODOO_DB, uid, odoo_pass,
                "hr.employee", "search_read",
                [[["user_id", "=", uid]]],
                {"fields": ["id", "name", "parent_id"]}
            )

            employee = employees[0] if employees else {}
            manager = {}

            # 3. Locate assigned manager if present
            if employee and employee.get("parent_id"):
                manager_id = employee["parent_id"][0]
                managers = models.execute_kw(
                    ODOO_DB, uid, odoo_pass,
                    "hr.employee", "read",
                    [manager_id],
                    {"fields": ["id", "name"]}
                )
                manager = managers[0] if managers else {}

            return {
                "categories": categories,
                "employee": employee,
                "manager": manager
            }
        except Exception as e:
            logger.error(f"Odoo dropdown fetch failed: {str(e)}")
            return {"error": str(e)}



    def create_expense(self, odoo_user, odoo_pass, ocr_text, content_json, receipt_image_b64):
 
        if MODE_LLM_CREATE_ODOO_EXPENSE_EXCEPTION == True:
            raise ValueError("MODE_LLM_CREATE_ODOO_EXPENSE_EXCEPTION")

        try:
            # Step 1: Convert image for diagnostics
            image_bytes, image_hash, gray_image_bytes, gray_image_b64 = convert_b64_to_bytes_and_gray(receipt_image_b64)

            # Step 2: Fetch dropdowns
            expense_dropdowns = self.fetch_dropdowns(odoo_user, odoo_pass)
            if "error" in expense_dropdowns:
                return {"error": f"Failed fetching dropdown metadata: {expense_dropdowns['error']}"}

            # Step 3: Use provided content_json (already parsed by LLM)
            _summary_json = content_json.get("summary", {})
            _details_json = content_json.get("details", [])

            # Step 4: Save diagnostics
            filename = f"receipt_{image_hash[:10]}.jpg"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            preocr_filepath = os.path.join(UPLOAD_FOLDER, f"preocr_{filename}")
            with open(filepath, "wb") as f:
                f.write(image_bytes)
            cv2.imwrite(preocr_filepath, gray_image_bytes)

            # Step 5: Build payloads
            category_id = expense_dropdowns["categories"][0]["id"] if expense_dropdowns.get("categories") else None
            employee_id = expense_dropdowns["employee"]["id"] if expense_dropdowns.get("employee") else None

            notes_text = "\n".join(
                f"{d.get('item', 'Item')} - {d.get('price_unit', 0)} x {d.get('quantity', 1)}"
                for d in _details_json
            )

            expense_payload = {
                "automation_monitor": True,
                "name": _summary_json.get("name", "Expense Record"),
                "total_amount": _summary_json.get("total_amount", 0.0),
                "date": _summary_json.get("date", datetime.today().strftime("%Y-%m-%d")),
                "payment_mode": _summary_json.get("paid_by", "own_account"),
                "description": notes_text,
            }
            if category_id: expense_payload['product_id'] = category_id
            if employee_id: expense_payload['employee_id'] = employee_id
            expense_payload = {k: v for k, v in expense_payload.items() if v is not None}

            monitor_payload = {
                "module": "expense",
                "raw_image": receipt_image_b64,
                "preocr_image": gray_image_b64,
                "ocr_text": ocr_text,
                "ocr_json": content_json,
                "status": _summary_json.get("status"),
                "confidence": _summary_json.get("confidence_level", 0.0),
                "message": _summary_json.get("message"),
                "remark": _summary_json.get("remark"),
                "image_hash": image_hash,
            }
            monitor_payload = {k: v for k, v in monitor_payload.items() if v is not None}

            # Step 6: Push to Odoo
            uid, models = self._get_models(odoo_user, odoo_pass)
            res = models.execute_kw(
                ODOO_DB, uid, odoo_pass,
                "hr.expense", "create_with_monitor",
                [expense_payload, monitor_payload]
            )
            expense_id, monitor_id = res[0], res[1]

            # Step 7: Attach receipt
            attached = False
            if expense_id:
                models.execute_kw(
                    ODOO_DB, uid, odoo_pass,
                    'ir.attachment', 'create',
                    [{
                        'name': f"Receipt_{expense_id}",
                        'res_model': 'hr.expense',
                        'res_id': expense_id,
                        'type': 'binary',
                        'datas': receipt_image_b64,
                    }]
                )
                attached = True

            return {
                "status": "success",
                "expense_id": expense_id,
                "monitor_id": monitor_id,
                "attachment_uploaded": attached,
                "content_json": content_json
            }

        except Exception as e:
            logger.error(f"E2E Expense Orchestrator execution collapsed: {str(e)}")
            return {"error": str(e)}




    # === Internal Core Utility Workers ===
 
    def _get_models(self, odoo_user, odoo_pass):
        common = xmlrpc.client.ServerProxy(f"{ODOO_BASE_URL}/xmlrpc/2/common")
        uid = common.authenticate(ODOO_DB, odoo_user, odoo_pass, {})
        if not uid:
            raise PermissionError("Failed authentication checks against Odoo base instance.")
        models = xmlrpc.client.ServerProxy(f"{ODOO_BASE_URL}/xmlrpc/2/object")
        return uid, models