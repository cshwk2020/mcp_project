import pytest
import json
import requests
import datetime
from mcp_project.xero_config import (
    load_xero_tokens, refresh_tokens, get_access_token,
    connectionAPI, xero_tenant_id, xero_tokens, 
    XERO_INVOICES_URL, XERO_MANUAL_JOURNAL_URL
)
from mcp_project.mcp_servers.mcp_api_sync.mcp_xero_sync_service import MCPXeroSyncService


@pytest.fixture(scope="module")
def xero_sync_service():
    return MCPXeroSyncService()
 


@pytest.mark.skip(reason="temporarily disabled")
def test_delete_all_invoices(xero_sync_service):
    global xero_tenant_id, xero_tokens
    refresh_tokens()      
    xero_tokens = load_xero_tokens()  
    access_token = xero_tokens['access_token']       
    xero_tenant_id = connectionAPI()  

    xero_sync_service.delete_all_invoices(access_token, xero_tenant_id)



@pytest.mark.skip(reason="temporarily disabled")
def test_delete_all_COGS(xero_sync_service):
    global xero_tenant_id, xero_tokens
    refresh_tokens()      
    xero_tokens = load_xero_tokens()  
    access_token = xero_tokens['access_token']       
    xero_tenant_id = connectionAPI()  

    xero_sync_service.delete_all_COGS(access_token, xero_tenant_id)


@pytest.mark.skip(reason="temporarily disabled")
def test_pull_payloads(xero_sync_service):
    global xero_tenant_id, xero_tokens
    refresh_tokens()      
    xero_tokens = load_xero_tokens()   
    access_token = xero_tokens['access_token']             
    xero_tenant_id = connectionAPI()  

    payloads = xero_sync_service.pull_odoo_sale_orders_and_pickings() 
    print("test_pull_payloads...payloads==", payloads)
 

@pytest.mark.skip(reason="temporarily disabled")
def test_sync_all_transactions(xero_sync_service):
    #
    global xero_tenant_id, xero_tokens
    refresh_tokens()      
    xero_tokens = load_xero_tokens()  
    access_token = xero_tokens['access_token']              
    xero_tenant_id = connectionAPI()  
    #
    xero_sync_service.delete_all_invoices(access_token, xero_tenant_id)
    xero_sync_service.delete_all_COGS(access_token, xero_tenant_id)
    #
    #xero_sync_service.sync_all_transactions(access_token, xero_tenant_id)

##########################################################

TEST_INVOICE_ID = 8150

@pytest.mark.skip(reason="temporarily disabled")
def test_xero_api_update_invoice():
    global xero_tenant_id, xero_tokens
    refresh_tokens()
    xero_tokens = load_xero_tokens()
    xero_tenant_id = connectionAPI()

    headers = {
        "Authorization": f"Bearer {xero_tokens['access_token']}",
        "xero-tenant-id": xero_tenant_id,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "Type": "ACCREC",
        "Contact": {"Name": "Test Contact"},
        "Date": datetime.date.today().isoformat(),
        "DueDate": (datetime.date.today() + datetime.timedelta(days=14)).isoformat(), 
        "InvoiceNumber": f"{TEST_INVOICE_ID}",
        "Status": "AUTHORISED",
        "LineItems": [
            {"Description": "Test Item", "Quantity": 1, "UnitAmount": 100, "AccountCode": "200"}
        ]
    }

    # 查有冇已存在 Invoice
    #check_url = f"{XERO_INVOICES_URL}?InvoiceNumber=88149148"
    check_url = f"{XERO_INVOICES_URL}?where=InvoiceNumber==\"{TEST_INVOICE_ID}\""
    check_resp = requests.get(check_url, headers=headers)
    data = check_resp.json()

    print("\n\nsync_Invoices...GET...\n", data)

    if data.get("Invoices"):
        print("sync_Invoices...UPDATE IS POST...")
        invoice_id = data["Invoices"][0]["InvoiceID"]
        payload["InvoiceID"] = invoice_id
        update_payload = {
            "Invoices": [payload]   # 必須用 array
        }
         
        update_url = XERO_INVOICES_URL
        response = requests.post(update_url, json=update_payload, headers=headers)

    else:
        print("sync_Invoices...CREATE IS PUT...")
        response = requests.put(XERO_INVOICES_URL, json=payload, headers=headers)


    print("DEBUG status_code==", response.status_code)


    if response.status_code not in (200, 201):
        print("Error sync Invoices:", response.status_code, response.text)
        response.raise_for_status()

    try:
        print("sync_invoice...JSON...")
        data = response.json()
        print("Invoices response:", json.dumps(data, indent=2))
        #assert "Invoices" in data, "No COGS key in response"
    except Exception:
        print("Invoices response (raw XML):", response.text)
        pytest.fail("InvoicesAPI did not return JSON")



@pytest.mark.skip(reason="temporarily disabled")
def test_xero_api_update_cogs():
    global xero_tenant_id, xero_tokens
    refresh_tokens()
    xero_tokens = load_xero_tokens()
    xero_tenant_id = connectionAPI()

    headers = {
        "Authorization": f"Bearer {xero_tokens['access_token']}",
        "xero-tenant-id": xero_tenant_id,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    journal_payload = {
        "Narration": "COGS entry for Air Purifier 2026",
        "Date": datetime.date.today().isoformat(),
        "Status": "POSTED",
        "ManualJournalID": f"{TEST_INVOICE_ID}",
        "Reference": f"{TEST_INVOICE_ID}",
        "JournalLines": [
            {"Description": "Air Purifier 2026", "AccountCode": "310", "LineAmount": 160.0},
            {"Description": "Inventory Asset Clearing", "AccountCode": "630", "LineAmount": -160.0}
        ]
    }

    # 拉全部 journals，再用 Python filter
    check_url = XERO_MANUAL_JOURNAL_URL
    check_resp = requests.get(check_url, headers=headers)
    data = check_resp.json()
    journals = data.get("ManualJournals", [])

    print("COGS...check...journals == ", journals)

    existing_journal = next(
        (j for j in journals if j.get("JournalNumber") == str(TEST_INVOICE_ID)),
        None
    )
    print("COGS...check...existing_journal == ", existing_journal)

    if existing_journal:
        print("COGS...update...POST...")
        journal_payload["ManualJournalID"] = existing_journal["ManualJournalID"]
        update_payload = {"ManualJournals": [journal_payload]}
        response = requests.post(XERO_MANUAL_JOURNAL_URL, json=update_payload, headers=headers)
    else:
        print("COGS...CREATE...PUT...")
        response = requests.put(XERO_MANUAL_JOURNAL_URL, json={"ManualJournals":[journal_payload]}, headers=headers)

    print("DEBUG status_code==", response.status_code)

    if response.status_code not in (200, 201):
        print("Error sync COGS journal:", response.status_code, response.text)
        response.raise_for_status()

    try:
        data = response.json()
        print("COGS Journal response:", json.dumps(data, indent=2))
    except Exception:
        print("COGS Journal response (raw XML):", response.text)
        pytest.fail("ManualJournal API did not return JSON")
