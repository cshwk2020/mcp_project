import json
import pytest
from mcp_project.mcp_servers.mcp_api_sync.mcp_xero_sync_contact_service import MCPXeroSyncContactService
from mcp_project.mcp_shared.mcp_odoo_client import MCPOdooClient
from mcp_project.xero_config import (
    load_xero_tokens, refresh_tokens, get_access_token,
    connectionAPI, xero_tenant_id, xero_tokens
)

@pytest.fixture(scope="module")
def odoo_client():
    return MCPOdooClient()

@pytest.fixture(scope="module")
def xero_contact_service(odoo_client):
    return MCPXeroSyncContactService(odoo_client)


@pytest.mark.skip(reason="temporarily disabled")
def test_pull_contacts_from_odoo(odoo_client):
    """
    Standalone test: pull contacts from Odoo and verify structure.
    """
    contacts = odoo_client.get_contacts(limit=5)
    print("contacts==", contacts)

    assert isinstance(contacts, list)
    assert len(contacts) > 0
    assert "name" in contacts[0]
    assert "email" in contacts[0]


@pytest.mark.skip(reason="temporarily disabled")
def test_sync_all_contacts_to_xero(xero_contact_service):
    global xero_tenant_id, xero_tokens
    refresh_tokens()      
    xero_tokens = load_xero_tokens()   
    access_token = xero_tokens['access_token']             
    xero_tenant_id = connectionAPI()  

    results = xero_contact_service.sync_all_contacts(access_token, xero_tenant_id)
    print("sync Contact results==", results)

    # Basic assertions: ensure API call returned something
    assert isinstance(results, list)
   
