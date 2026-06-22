import os
import json 
import requests
import urllib
from mcp_project.mcp_shared.vault_util import VaultUtil 
#
_vault = VaultUtil()
#####################################################
XERO_EMAIL = _vault.get_xero_email()
XERO_USERNAME = _vault.get_xero_username()
XERO_PASSWORD = _vault.get_xero_password()
#####################################################
XERO_CLIENT_ID = _vault.get_xero_client_id()
XERO_CLIENT_SECRET = _vault.get_xero_client_secret()
XERO_REDIRECT_URI = "http://localhost:8000/api/sync/odoo2xero"
#####################################################
XERO_AUTHORIZE_BASE_URL = "https://login.xero.com/identity/connect/authorize"
XERO_CONNECTION_URL = "https://api.xero.com/connections"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
xero_tokens = {}
xero_tenant_id = None
XERO_AUTH_CODE = None  
#####################################################
XERO_INVOICE_URL = "https://api.xero.com/api.xro/2.0/Invoices"
XERO_MANUAL_JOURNAL_URL = "https://api.xero.com/api.xro/2.0/ManualJournals"
XERO_AccountCode_COGS = "310"
XERO_AccountCode_Inventory = "630"
#####################################################
CONFIG_BASE_PATH = "/Volumes/sdcard/PORTFOLIO_2026/PY3.10_BASE/mcp_project"


def save_xero_tokens():
    TOKEN_FILE = os.path.join(CONFIG_BASE_PATH, "xero_tokens.json")
    with open(TOKEN_FILE, "w") as f:
        json.dump(xero_tokens, f)

def load_xero_tokens():
    global xero_tokens
    try:
        TOKEN_FILE = os.path.join(CONFIG_BASE_PATH, "xero_tokens.json")
        with open(TOKEN_FILE) as f:
            xero_tokens = json.load(f)
            print("load_xero_tokens...xero_tokens==", xero_tokens)
    except FileNotFoundError:
        xero_tokens = {}

    return xero_tokens


def build_authorize_url():
    #base_url = "https://login.xero.com/identity/connect/authorize"
    
    # Define valid, clean scopes as a list to avoid hidden white-space/newline issues
    scope_list = [
        "openid",
        "profile",
        "email",
        "offline_access",
        "accounting.invoices",   
        "accounting.invoices.read", 
        "accounting.manualjournals",
        "accounting.manualjournals.read",
        "accounting.contacts",
        "accounting.contacts.read",
    ]
 
    
    params = {
        "response_type": "code",
        "client_id": XERO_CLIENT_ID,
        "redirect_uri": XERO_REDIRECT_URI,
        "scope": " ".join(scope_list),  # Joins cleanly with exactly one space
        "state": "123"
    }
    return f"{XERO_AUTHORIZE_BASE_URL}?{urllib.parse.urlencode(params)}"


 
def get_initial_tokens(auth_code):
    #token_url = "https://identity.xero.com/connect/token"
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": XERO_REDIRECT_URI,
        "client_id": XERO_CLIENT_ID,
        "client_secret": XERO_CLIENT_SECRET
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(XERO_TOKEN_URL, data=data, headers=headers)
    response.raise_for_status()
    xero_tokens.update(response.json())
    save_xero_tokens()
    print("Initial xero_tokens:", xero_tokens)


def refresh_tokens():
    global xero_tokens
    xero_tokens = load_xero_tokens()
    #token_url = "https://identity.xero.com/connect/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": xero_tokens.get("refresh_token"),
        "client_id": XERO_CLIENT_ID,
        "client_secret": XERO_CLIENT_SECRET
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(XERO_TOKEN_URL, data=data, headers=headers)
    response.raise_for_status()
    xero_tokens.update(response.json())
    save_xero_tokens()
    print("Refreshed xero_tokens:", xero_tokens)


def get_access_token():
    """自動檢查 access_token 是否存在，必要時 refresh"""
    if "access_token" not in xero_tokens:
        get_initial_tokens()
    else:
        refresh_tokens()
    return xero_tokens["access_token"]


def connectionAPI():
    """拉取 Tenant ID"""
    global xero_tenant_id
    #url = "https://api.xero.com/connections"
    headers = {
        "Authorization": f"Bearer {xero_tokens['access_token']}",
        "Content-Type": "application/json"
    }
    response = requests.get(XERO_CONNECTION_URL, headers=headers)
    if response.status_code != 200:
        print("Error fetching connections:", response.status_code, response.text)
        response.raise_for_status()
    data = response.json()
    print("Connections:", data)
    xero_tenant_id = data[0]["tenantId"]
    return xero_tenant_id


# http://localhost:8000/api/sync/odoo2xero?code=fyQnKtYEegsFprwphDe-5JSdDKfXHYX6GizR3hxASd4&scope=openid%20profile%20email%20offline_access%20accounting.invoices%20accounting.contacts&state=123&session_state=DiUJ_Gzy-yCJDFrGvv47TjXAyZy4AF_5d3ddpq3_Klk.99D9A0DBF92FE3F73EACC9F2B1D4FFA2
"""
https://login.xero.com/identity/connect/authorize?response_type=code&client_id=BFFAF1576AA9423F833DF4A4730A06C1&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fsync%2Fodoo2xero&scope=openid+profile+email+offline_access+accounting.invoices+accounting.contacts&state=123
"""
def test_get_code_url():
    url = build_authorize_url()
    print("url == ", url)

if __name__ == '__main__':
     full_authorize_url = build_authorize_url()
     print("full_authorize_url==", full_authorize_url)
     # https://login.xero.com/identity/connect/authorize?response_type=code&client_id=BFFAF1576AA9423F833DF4A4730A06C1&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fsync%2F






