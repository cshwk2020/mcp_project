import requests
import logging
from mcp_project.xero_config import XERO_CONTACTS_URL

class MCPXeroSyncContactService:

    def __init__(self, odoo_client):
        self.service_name = "Odoo → Xero Contact Sync MCP Server"
        self.odoo_client = odoo_client

    def get_tools_schema(self):
        return [
            {
                "name": "sync_all_contacts",
                "description": "Sync all active contacts (vendors/customers) from Odoo into Xero.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "access_token": {"type": "string", "description": "Fresh Xero OAuth2 access token"},
                        "tenant_id": {"type": "string", "description": "Xero tenant ID"}
                    },
                    "required": ["access_token", "tenant_id"]
                }
            }
        ]

    def _get_xero_contact(self, contact, access_token, tenant_id):
        """Check if contact already exists in Xero by Email or AccountNumber."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Accept": "application/json"
        }

        email = contact.get("email")
        account_number = f"ODOO-{contact.get('id')}"

        queries = []
        if email:
            queries.append(f"EmailAddress==\"{email}\"")
        if account_number:
            queries.append(f"AccountNumber==\"{account_number}\"")

        for q in queries:
            url = f"{XERO_CONTACTS_URL}?where={q}"
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                if data.get("Contacts"):
                    return data["Contacts"][0]
            except Exception as e:
                logging.error(f"Xero API Contact lookup error: {str(e)}")

        return None

    def _post_to_xero(self, payload, access_token, tenant_id):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "xero-tenant-id": tenant_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        try:
            print(">>> _post_to_xero PRE_SYNC Contact payload:", payload)
            response = requests.post(XERO_CONTACTS_URL, json=payload, headers=headers)
            print(">>> _post_to_xero SYNC Contact status:", response.status_code)
            response.raise_for_status()
            print(">>> _post_to_xero POST_SYNC Contact response:", response.json())
            return response.json()
        except Exception as e:
            print(">>> _post_to_xero POST_SYNC Contact Exception:", e)
            if hasattr(e, 'response') and e.response is not None:
                print(">>> Xero Contact error body:", e.response.text)
            logging.error(f"Xero API Contact error: {str(e)}")
            return None

    def _build_xero_contact_payload(self, contact):
        address_info = contact.get("address", {})
        return {
            "Name": contact.get("name"),
            "EmailAddress": contact.get("email", ""),
            "AccountNumber": f"ODOO-{contact.get('id')}",  # 唯一代碼
            "Phones": [
                {
                    "PhoneType": "DEFAULT",
                    "PhoneNumber": contact.get("phone", "")
                }
            ],
            "Addresses": [
                {
                    "AddressType": "POBOX",
                    "AddressLine1": address_info.get("street", ""),
                    "City": address_info.get("city", ""),
                    "PostalCode": address_info.get("zip", ""),
                    "Country": address_info.get("country", "")
                }
            ]
        }

    def sync_contact(self, contact, access_token, tenant_id):
        print(">>> sync_contact PRE_SYNC Contact:", contact)
        existing = self._get_xero_contact(contact, access_token, tenant_id)
        if existing:
            print(f"Contact '{contact.get('name')}' already exists in Xero, ContactID={existing['ContactID']}")
            # ✅ 用 ref 存 ContactID
            self.odoo_client.models.execute_kw(
                self.odoo_client.db, self.odoo_client.uid, self.odoo_client.odoo_pass,
                'res.partner', 'write',
                [[contact["id"]], {"ref": f"XERO:{existing['ContactID']}"}]
            )
            return existing

        payload = {"Contacts": [self._build_xero_contact_payload(contact)]}
        result = self._post_to_xero(payload, access_token, tenant_id)
        if result and result.get("Contacts"):
            contact_id = result["Contacts"][0]["ContactID"]
            print(f"New Contact created in Xero, ContactID={contact_id}")
            # ✅ 用 ref 存 ContactID
            self.odoo_client.models.execute_kw(
                self.odoo_client.db, self.odoo_client.uid, self.odoo_client.odoo_pass,
                'res.partner', 'write',
                [[contact["id"]], {"ref": f"XERO:{contact_id}"}]
            )
        print(">>> sync_contact POST_SYNC result:", result)
        return result

    def sync_all_contacts(self, access_token, tenant_id):
        print(">>> sync_all_contacts PRE_SYNC fetching contacts...")
        contacts = self.odoo_client.get_contacts()

        valid_contacts = []
        for contact in contacts:
            name = (contact.get("name") or "").strip()
            if not name:
                print(f"Skipping contact ID '{contact.get('id')}' - Missing Name.")
                continue
            valid_contacts.append(contact)

        if not valid_contacts:
            print("No valid Contacts to sync after filtering.")
            return []

        results = []
        for contact in valid_contacts:
            result = self.sync_contact(contact, access_token, tenant_id)
            if result:
                results.append(result)

        return results
