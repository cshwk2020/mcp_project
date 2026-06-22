import json
import pytest
from mcp_project.mcp_servers.mcp_api_sync.mcp_odoo_sync_service import MCPOdooSyncService

@pytest.fixture(scope="module")
def odoo_sync_service():
    return MCPOdooSyncService()


@pytest.mark.skip(reason="temporarily disabled")
def test_sync_woocommerce_orders_full_fields(odoo_sync_service):

    """
    fake_orders = [{
        "status": "completed",
        "id": 150,
        "currency": "HKD",
        "order_key": "wc_order_5FgeCkP48b5W2",
        "date_created": "2026-05-28T18:28:27",
        "date_completed": None,
        "total": "100.00",
        "total_tax": "0.00",
        "shipping_total": "20.00",
        "payment_method": "cod",
        "payment_method_title": "Cash on delivery",
        "customer_note": "Please deliver after 6pm",
        "billing": {
            "first_name": "Hung",
            "last_name": "WK",
            "company": "Test Ltd",
            "address_1": "Flat A",
            "address_2": "Block 1",
            "city": "Kowloon",
            "state": "KOWLOON",
            "postcode": "HK",
            "country": "HK",
            "email": "cshwk2020@gmail.com",
            "phone": "12345678"
        },
        "shipping": {
            "first_name": "Hung",
            "last_name": "WK",
            "address_1": "Flat A",
            "city": "Kowloon",
            "state": "KOWLOON",
            "postcode": "HK",
            "country": "HK",
            "phone": "12345678"
        },
        "line_items": [
            {
                "sku": "HM008",
                "name": "Air Purifier 2026",
                "quantity": 1,
                "price": 80,
                "subtotal": "80.00",
                "total": "80.00"
            }
        ],
        "shipping_lines": [
            {
                "method_title": "Flat rate",
                "total": "20.00"
            }
        ]
    }]
    """

    fake_orders = []
    with open("./test_data/woo_order.json") as f:
        fake_orders = json.load(f) 
        print("fake_orders==", fake_orders)


    result = odoo_sync_service.sync_woocommerce_orders_to_odoo(fake_orders, warehouse_code="whwoo")
    print("sync result:", result)

    assert result["status"] == "success"
    assert result["results"][0]["sale_order_id"] > 0
