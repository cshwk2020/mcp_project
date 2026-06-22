
import os

# from .vault_utils import mock_get_odoo_user, mock_get_odoo_pass, mock_get_deepseek_key
from mcp_project.mcp_shared.vault_util import VaultUtil 

#
_vault = VaultUtil()

#
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

#
LOGGER_FILE_PATH = os.path.join(UPLOAD_FOLDER, "api.log")
 

# AI DEEPSEEK
LLM_API_MODEL_VER = "deepseek-v4-flash"
LLM_API_KEY = _vault.get_deepseek_key()
LLM_API_URL = "https://api.deepseek.com/chat/completions"


# ODOO SETTING
ODOO_BASE_URL = "http://localhost:8069"
ODOO_DB = "odoo"


# microservice flask 
MS_BASE_URL = "http://127.0.0.1:5000"

# REAL AI CALL OR MOCK 
MODE_REAL = False
MODE_OCR_EXCEPTION = False
MODE_LLM_PARSE_OCR_EXCEPTION = False
MODE_LLM_CREATE_ODOO_EXPENSE_EXCEPTION = False

# MOCK OCR Output to save dev time 
MOCK_FILE_PATH = "/Users/cshwk1995/Desktop/img/receipts/IMG_2150.jpg"
MOCK_FAIL_FILE_PATH = "/Users/cshwk1995/Desktop/img/receipts/non_image_txt.jpg"
MOCK_FILE_OCR_TEXTS = ['1393', '缸轟中心1#:27643118', '四州鼠苜牛廂蠣五包裝', '40. 00', '火船牌三合-白吻味1OPC', '17. 50', '51. 50', '00', '低a#', '儻', '-6.0', '輒"付a0', '57. 50', '0. 00', '襯', '100. 00', '42. 5(', '25042026/18:54/0807/002/3985/00002406', '2504260004980023985', '虫即日起至2026年5月21日於門市或惠康網', '店買滿$50,即可掃d? Code參加初夏派禮大', '抽獎,齊抽八一萬份獎品,其中包括豈曾獎', '品及僂患/現金券 受條款及細則約束.', 'Jiin', 'the Wlellcome Early Summer Lucky', 'Draw;', 'Spend $50', 'at physical', 'stores', 'or', 'online shop', 'and', 'scan', 'the OR', 'code below', 'to join', 'the', 'lucky', 'draw', 'from', 'today', 't0', '21', 'nay.', '800k', 'prizes,', 'including', 'freebies', 'and', 'coupon$,', 'await', 'Terms', 'and', 'conditions appiy.', '', 'voul']
MOCK_FILE_LLM_JSON = {
    "summary": {
        "total_amount": 57.5,
        "employee": "Tester1",
        "manager": "",
        "paid_by": "own_account",
        "name": "Receipt from Wellcome",
        "date": "2026-04-25",
        "category": "Food",
        "confidence_level": 0.7,
        "status": "complete",
        "remark": "OK"
    },
    "details": [
        {
        "price_unit": 40.0,
        "quantity": 1,
        "item": "四洲蘿荀牛瞞麵五包裝"
        },
        {
        "price_unit": 17.5,
        "quantity": 1,
        "item": "火船牌三合一白咖啡10PC"
        }
    ]
}


"""
{
    "summary": {
        "total_amount": 3.2,
        "employee": "Tester1",
        "manager": "Administrator",
        "paid_by": "own_account",
        "name": "Receipt from 佳寶",
        "date": "2026-04-11",
        "category": "FOOD",
        "confidence_level": 0.9
    },
    "details": [
        {
        "price_unit": 4.0,
        "quantity": 1,
        "item": "芬達橙味汽水330ml"
        }
    ]
}
"""

"""
{
    "summary": {
        "total_amount": 50.0,
        "employee": "Tester1",
        "paid_by": "own_account",
        "name": "Receipt from Wellcome",
        "date": "2026-05-02",
        "category": "FOOD",
        "confidence_level": 0.85
    },
    "details": [
        {
        "price_unit": 50.0,
        "quantity": 1,
        "item": "四洲蘿薊牛腑麵五包裝"
        }
    ]
}
"""

"""
{
    "summary": {
        "total_amount": 57.5,
        "employee": "Tester1",
        "manager": "Administrator",
        "paid_by": "own_account",
        "name": "Receipt from Wellcome",
        "date": "2026-04-25",
        "category": "FOOD",
        "confidence_level": 0.8
    },
    "details": [
        {
        "price_unit": 17.5,
        "quantity": 1,
        "item": "四洲蘿荀牛瞞麵五包裝"
        },
        {
        "price_unit": 40.0,
        "quantity": 1,
        "item": "火船牌三合一白咖啡10PC"
        }
    ]
}
"""
