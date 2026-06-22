from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

class SyncOdooState(TypedDict):
    session_id: str
    mcp_client: object
    system_name: str
    resource_type: str
    result: List[Dict[str, Any]]
    error: str

def check_orders_remaining(state: SyncOdooState) -> str:
    return "has_orders" if state["result"] else "no_orders"

# --- Node A: 拉 Shopify 訂單 ---
async def run_shopify_orders_node(state: SyncOdooState) -> dict:
    try:
        sync_state = await state["mcp_client"].call_tool(
            "odoo_get_sync_state",
            {"system_name": state["system_name"], "resource_type": state["resource_type"]}
        )
        last_sync_time = sync_state.get("last_sync_time")
        last_sync_id = sync_state.get("last_sync_id")

        response = await state["mcp_client"].call_tool(
            "shopify_fetch_orders",
            {"after": last_sync_time, "since_id": last_sync_id}
        )
        result_payload = response.get("result", {}) if "result" in response else response
        if not result_payload or "error" in result_payload:
            return {"error": result_payload.get("error", "Shopify fetch failed"), "node": "shopify_orders"}

        orders = result_payload.get("orders", [])
        state["result"] = orders
        return {"result": orders, "node": "shopify_orders"}
    except Exception as e:
        return {"error": f"Shopify node failed: {e}", "node": "shopify_orders"}

# --- Node BC: Upsert Invoice + Delta Inventory ---
async def run_order_sync_node(state: SyncOdooState) -> dict:
    try:
        order = state["result"].pop(0)   # ✅ shrink list
        resp = await state["mcp_client"].call_tool(
            "odoo_sync_order",   # 單一 XMLRPC call：Invoice + Inventory
            {
                "system_name": state["system_name"],
                "resource_type": state["resource_type"],
                "order": order,
                "warehouse": "shopify_wh"
            }
        )
        payload = resp.get("result", {}) if "result" in resp else resp
        if "error" in payload:
            return {"error": payload["error"], "node": "order_sync"}

        # ✅ 更新 sync.state → 保證進度前移
        await state["mcp_client"].call_tool(
            "odoo_update_sync_state",
            {
                "system_name": state["system_name"],
                "resource_type": state["resource_type"],
                "last_sync_time": order.get("updated_at"),
                "last_sync_id": order.get("id")
            }
        )

        return {"last_order": order, "sync_result": payload, "node": "order_sync"}
    except Exception as e:
        return {"error": f"Order sync failed: {e}", "node": "order_sync"}

# --- Node D: 完成 ---
async def run_done_node(state: SyncOdooState) -> dict:
    return {"node": "done"}

# --- Graph 組裝 ---
def create_sync_shopify_orders_graph():
    workflow = StateGraph(SyncOdooState)
    workflow.add_node("shopify_orders", run_shopify_orders_node)
    workflow.add_node("order_sync", run_order_sync_node)
    workflow.add_node("done", run_done_node)

    workflow.set_entry_point("shopify_orders")

    # A → BC (有訂單) / A → D (冇訂單)
    workflow.add_conditional_edges("shopify_orders", check_orders_remaining,
        {"has_orders": "order_sync", "no_orders": "done"})

    # BC → BC (仲有訂單) / BC → D (冇訂單)
    workflow.add_conditional_edges("order_sync", check_orders_remaining,
        {"has_orders": "order_sync", "no_orders": "done"})

    workflow.add_edge("done", END)

    return workflow.compile()

