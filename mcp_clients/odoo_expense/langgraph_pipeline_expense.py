import base64
import io, sys
from PIL import Image
from typing import TypedDict
from langgraph.graph import StateGraph, END
from mcp_project.mcp_shared.debug_log_queue import push_log

class ExpenseState(TypedDict):
    session_id: str
    image_b64: str
    ocr_text: str
    content_json: dict
    final_response: dict
    mcp_client: object
    error: str

def check_for_errors(state: ExpenseState) -> str:
    """
    Checks the unified state layout for logged crash vectors.
    If an error is found, it forces a sideways abort to END.
    """
    if state.get("error"):
        return "abort_to_end"
    return "proceed_next"

 
async def run_start_node(state: ExpenseState) -> dict:
    try:
        img_b64 = state.get("image_b64")
        if not img_b64:
            return {"error": "No uploaded image found", "node": "start_node"}

        # 嘗試 decode base64
        try:
            img_bytes = base64.b64decode(img_b64)
            Image.open(io.BytesIO(img_bytes)).verify()  # PIL verify
        except Exception:
            return {"error": "Invalid or corrupted image", "node": "start_node"}

        return {
            "session_id": state["session_id"],
            "image_b64": img_b64,
            "node": "start_node"
        }

    except Exception as e:
        return {"error": f"Start node failed: {e}", "node": "start_node"}



async def run_ocr_node(state: ExpenseState) -> dict:

    push_log("DEBUG/c/langgraph...run_ocr_node...0...")
 
    try:
        mcp_client = state["mcp_client"]
        if not state.get("image_b64"):
            return {"error": "Missing base64 asset stream context.", "node": "easyocr_step"}

        push_log("DEBUG/c/langgraph...run_ocr_node...10...")
 
        response = await mcp_client.call_tool("ocr_run_bytes_b64", {"image_bytes": state["image_b64"]})
        
        push_log("DEBUG/c/langgraph...run_ocr_node...20...")

        result_payload = response.get("result", {}) if "result" in response else response

        # payload error
        if isinstance(result_payload, dict) and "error" in result_payload:
            return {"error": result_payload["error"], "node": "easyocr_step"}

        texts = result_payload.get("texts", [])
        if not texts:
            return {"error": "OCR returned no text", "node": "easyocr_step"}

        return {"ocr_text": "\n".join(texts), "node": "easyocr_step"}

    except Exception as e:
        print(f"DEBUG...exception caught: {e}")
        return {"error": str(e), "node": "easyocr_step"}



async def run_llm_node(state: ExpenseState) -> dict:

    try:
        if state.get("error"):
            return {"error": state["error"], "node": "deepseek_step"}
        from mcp_project.mcp_shared.vault_util import VaultUtil
        _vault = VaultUtil()
        ocr_lines = state["ocr_text"].split("\n")
        response = await state["mcp_client"].call_tool(
            "llmprompt_extract_info_from_ocr_text",
            {
                "odoo_user": _vault.get_odoo_user(),
                "odoo_pass": _vault.get_odoo_pass(),
                "ocr_texts": ocr_lines
            }
        )
        result_payload = response.get("result", {}) if "result" in response else response

        # 新增檢查：LLM payload 有 error key
        if not result_payload or (
            isinstance(result_payload, dict) and "error" in result_payload
        ):
            err_msg = result_payload.get("error", "LLM failed to extract info")
            return {"error": err_msg, "node": "deepseek_step"}

        return {"content_json": result_payload, "node": "deepseek_step"}

    except Exception as e:
        return {"error": f"LLM step failed: {e}", "node": "deepseek_step"}



async def run_odoo_node(state: ExpenseState) -> dict:
    try:
        if state.get("error"):
            return {"error": state["error"], "node": "odoo_step"}
        from mcp_project.mcp_shared.vault_util import VaultUtil
        _vault = VaultUtil()
        params = {
            "odoo_user": _vault.get_odoo_user(),
            "odoo_pass": _vault.get_odoo_pass(),
            "ocr_text": state["ocr_text"],
            "content_json": state["content_json"],
            "receipt_image_b64": state["image_b64"]
        }
        response = await state["mcp_client"].call_tool("odoo_expense_create_expense", params)
        result_payload = response.get("result", {}) if "result" in response else response

        # ✅ 新增檢查：payload 有 error key
        if not result_payload or (
            isinstance(result_payload, dict) and "error" in result_payload
        ):
            err_msg = result_payload.get("error", "Odoo expense creation failed")
            return {"error": err_msg, "node": "odoo_step"}

        return {"final_response": result_payload, "node": "odoo_step"}
    except Exception as e:
        return {"error": f"Odoo step failed: {e}", "node": "odoo_step"}



def create_expense_graph():
    workflow = StateGraph(ExpenseState)
    workflow.add_node("start_node", run_start_node)
    workflow.add_node("easyocr_step", run_ocr_node)
    workflow.add_node("deepseek_step", run_llm_node)
    workflow.add_node("odoo_step", run_odoo_node)

    workflow.set_entry_point("start_node")

    workflow.add_conditional_edges("start_node", check_for_errors,
        {"proceed_next": "easyocr_step", "abort_to_end": END})
    workflow.add_conditional_edges("easyocr_step", check_for_errors,
        {"proceed_next": "deepseek_step", "abort_to_end": END})
    workflow.add_conditional_edges("deepseek_step", check_for_errors,
        {"proceed_next": "odoo_step", "abort_to_end": END})
    workflow.add_conditional_edges("odoo_step", check_for_errors,
        {"proceed_next": END, "abort_to_end": END})

    return workflow.compile()
