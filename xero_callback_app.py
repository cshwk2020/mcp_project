import os
import json
import requests
import urllib.parse
import time
from flask import Flask, request
app = Flask(__name__)

from mcp_project.xero_config import XERO_CLIENT_ID, XERO_CLIENT_SECRET, XERO_REDIRECT_URI
from mcp_project.xero_config import XERO_TOKEN_URL, XERO_AUTHORIZE_BASE_URL, CONFIG_BASE_PATH
from mcp_project.xero_config import load_xero_tokens, save_xero_tokens, get_access_token
from mcp_project.xero_config import xero_tenant_id
CODE_VERIFIER = None 

"""
https://login.xero.com/identity/connect/authorize?response_type=code&client_id=BFFAF1576AA9423F833DF4A4730A06C1&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fsync%2Fodoo2xero&scope=openid+profile+email+offline_access+accounting.items+accounting.items.read+accounting.invoices+accounting.invoices.read+accounting.manualjournals+accounting.manualjournals.read+accounting.contacts+accounting.contacts.read+accounting.payments+accounting.payments.read+accounting.banktransactions+accounting.banktransactions.read+accounting.attachments+accounting.attachments.read+accounting.reports.aged.read+accounting.reports.balancesheet.read+accounting.reports.banksummary.read+accounting.reports.budgetsummary.read+accounting.reports.executivesummary.read+accounting.reports.profitandloss.read+accounting.reports.trialbalance.read+accounting.reports.taxreports.read+accounting.reports.tenninetynine.read+payroll.employees+payroll.employees.read+payroll.payruns+payroll.payruns.read+payroll.payslip+payroll.payslip.read+payroll.settings+payroll.settings.read+payroll.timesheets+payroll.timesheets.read+files+files.read+assets+assets.read+projects+projects.read&state=123
"""

@app.route("/api/sync/odoo2xero", methods=["POST", "GET"])
def xero_callback():
 
    error = request.args.get('error')
    if error:
        return f"Authorization failed: {error}", 400
        
    auth_code = request.args.get('code')
    if not auth_code:
        return "Missing authorization code parameter.", 400

    print(f"\n[INFO] Intercepted valid code value: {auth_code}")
    print("Exchanging authentication token pairs with Xero...")
    
    #token_url = "https://identity.xero.com/connect/token"
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": XERO_REDIRECT_URI,
        "client_id": XERO_CLIENT_ID,
        "client_secret": XERO_CLIENT_SECRET
    }
    
    # Include your code verifier string in the payload if your app uses one
    if CODE_VERIFIER:
        data["code_verifier"] = CODE_VERIFIER

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(XERO_TOKEN_URL, data=data, headers=headers)
    
    if response.status_code != 200:
        return f"Exchange failed with error string: {response.text}", 400
        
    # Write the returned token payload securely to disk
    TOKEN_FILE = os.path.join(CONFIG_BASE_PATH, "xero_tokens.json")
    with open(TOKEN_FILE, "w") as f:
        json.dump(response.json(), f, indent=4)
        
    print("[SUCCESS] xero_tokens.json successfully created inside local workspace!")
    return "<h1>Success! You can close this browser window now. Your xero_tokens.json file has been written to disk.</h1>"

 
 
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
    tokens.update(response.json())
    save_tokens()
    print("Initial tokens:", tokens)



def refresh_tokens():
    load_tokens()
    #token_url = "https://identity.xero.com/connect/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": tokens.get("refresh_token"),
        "client_id": XERO_CLIENT_ID,
        "client_secret": XERO_CLIENT_SECRET
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(XERO_TOKEN_URL, data=data, headers=headers)
    response.raise_for_status()
    tokens.update(response.json())
    save_tokens()
    print("Refreshed tokens:", tokens)


if __name__ == '__main__':
    # Add your local link configuration execution line here
    app.run(port=8000)


