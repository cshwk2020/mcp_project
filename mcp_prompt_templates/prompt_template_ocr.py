from typing import List, Dict

def build_ocr_prompt_messages(
    ocr_text: str,
    employee_name: str,
    manager_name: str,
    categories_str: str) -> List[Dict[str, str]]:
 
    return [
            {
            "role": "system",
            "content": f"""
                You are a parser that converts messy OCR receipt text into JSON for Odoo ERP.
                Rules:
                - Output one JSON object with keys: summary, details.
                - summary must include these exact keys: total_amount, employee, manager, paid_by, name, date, category, confidence_level
                - Do not use synonyms like "total" or "amount", for example, always use "total_amount".
                - category must be inferred overall all items in the receipt (choose ONE from this list: {categories_str}).
                  Always try to classify most appropriate overall receipt category,
                  If a single category appear matching all items in same receipt, use that single category cover all items.
                  If multiple categories appear for vaious items in the same receipt, fallback to the generic EXP_GEN product.
                - details must list each line item with price_unit, quantity, and item text.
                - paid_by: either own_account OR company_account". 
                        Look for keywords like “Cash”, “Visa”, “MasterCard”, “Change”, etc. -> assume employee paid.
                        Look for “Company Card”, “Corporate Account”, “Paid by Company” -> assume company account.
                        If your OCR pipeline can’t detect payment mode reliably, you can default to "own_account" (since most receipts are employee‑paid) and allow manual override.
                - confidence_level: 0.00 - 1.00, based on applying all rules mentioned above, to ambiguity level of OCR output provided. 
                - status must be one of: "incomplete", "complete", "error".
                        "complete" if all required summary fields are present (total_amount, employee, paid_by, name, date, category) AND details list has at least one valid item.
                        "incomplete" if some required fields are missing or ambiguous (e.g. missing date, missing category, empty details).
                        "error" if the OCR text cannot be parsed into valid JSON at all, or if the receipt is unreadable.
                - if status is NOT complete, need explain reasons in remark field.


                - Return only valid JSON { ... } not list  [ ... ].
                """
            },

            {
                "role": "user",
                "content": f"""Here is the OCR output:
                    {ocr_text}\n\nEmployee Name: {employee_name}

                Return JSON as a list of expense records, each matching Odoo hr.expense fields:

                expense_json example format:
                {{
                    "summary": {{
                        "total_amount": 84,
                        "employee":  {employee_name},
                        "manager":  {manager_name},
                        "paid_by": "own_account | company_account",
                        "name": "Receipt from Wellcome",
                        "date": "2026-04-25",
                        "category": "XXXXXX",
                        "confidence_level": 0.00-1.00,
                        "status": incomplete | complete | error,
                        "remark": "OK",
                    }},
                    "details": [
                        {{"price_unit": 57.5, "quantity": 1, "item": "四洲蘿荀牛瞞麵五包裝 - 40.0\n火船牌三合一白咖啡10PC - 17.5"}},
                        {{"price_unit": 26.5, "quantity": 1, "item": "other item might or might not be food"}}
                    ]
                }}

        """
  
        }
          
    ] 