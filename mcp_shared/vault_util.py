import os
import hvac

class VaultUtil:
    
    def __init__(self, url=None, token=None):
        self.client = hvac.Client(
            url=url or os.environ.get("VAULT_ADDR"),
            token=token or os.environ.get("VAULT_TOKEN")
        )

    def get_secret(self, path: str) -> dict:
        return self.client.secrets.kv.read_secret_version(path=path)["data"]["data"]

    def get_odoo_user(self) -> str:
        """
        app_secrets = self.get_secret("app")
        odoo_user = app_secrets["odoo_user"]
        print("Odoo user:", odoo_user)
        return odoo_user
        """
        return "testuser1"

    def get_odoo_pass(self) -> str:
        """
        app_secrets = self.get_secret("app")
        odoo_pass = app_secrets["odoo_pass"]
        print("Odoo pass:", odoo_pass)
        return odoo_pass
        """
        return "51118326"

    def get_deepseek_key(self) -> str:
        """
        app_secrets = self.get_secret("app")
        deepseek_key = app_secrets["deepseek_key"]
        print("DeepSeek key:", deepseek_key)
        return deepseek_key
        """
        return "sk-8a42ed8789064093a279d6b1839a3241"


    def get_xero_email(self) -> str:
        """
        app_secrets = self.get_secret("app")
        xero_email = app_secrets["xero_email"]
        print("xero_email:", xero_email)
        return xero_email
        """
        return "cshwk2020@gmail.com"


    def get_xero_username(self) -> str:
        """
        app_secrets = self.get_secret("app")
        xero_username = app_secrets["xero_username"]
        print("xero_username:", xero_username)
        return xero_username
        """
        return "cshwk2020@gmail.com"

    def get_xero_password(self) -> str:
        """
        app_secrets = self.get_secret("app")
        xero_password = app_secrets["xero_password"]
        print("xero_password:", xero_password)
        return xero_password
        """
        return "2020pass2021@gmail.com"

    def get_xero_client_id(self) -> str:
        """
        app_secrets = self.get_secret("app")
        xero_client_id = app_secrets["xero_client_id"]
        print("xero_client_id:", xero_client_id)
        return xero_client_id
        """
        return "BFFAF1576AA9423F833DF4A4730A06C1"

    def get_xero_client_secret(self) -> str:
        """
        app_secrets = self.get_secret("app")
        xero_client_secret = app_secrets["xero_client_secret"]
        print("xero_client_secret:", xero_client_secret)
        return xero_client_secret
        """
        return "Ti4yxmcaOxzxvm0BHJ8kukW7YCxGp5uZJzmvX-qIH0vUTMl8"

  

