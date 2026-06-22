import pandas as pd

# --- Load Odoo export (XLS) ---
# Odoo export should contain: id, name, default_code
odoo_df = pd.read_excel("odoo_products.xlsx")

# --- Load WooCommerce export (CSV) ---
# Woo export should contain: id, name
woo_df = pd.read_csv("wc-product-export-id_name.csv")


# 正確欄位名：Odoo 用 "Name"，WooCommerce 用 "Name"
odoo_df["name_norm"] = odoo_df["Name"].str.strip().str.lower()
woo_df["name_norm"] = woo_df["Name"].str.strip().str.lower()

# Merge by name
mapping_df = pd.merge(
    odoo_df,
    woo_df,
    on="name_norm",
    suffixes=("_odoo", "_woo")
)

# 選需要的欄位
result = mapping_df[["Internal Reference", "Name_odoo", "ID", "name_norm"]]
result.columns = ["sku", "name", "id", "name_norm"]
result = result.drop(columns=["name_norm"])

# 儲存 mapping table
result.to_csv("odoo_woo_mapping.csv", index=False)
print("Mapping table created: odoo_woo_mapping.csv")
