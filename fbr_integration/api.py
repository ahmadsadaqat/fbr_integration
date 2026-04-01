import frappe
import requests
import json
from frappe import _

def send_to_fbr(doc, method=None):
    # 1. Fetch site-specific config
    config = frappe.conf.get("fbr_config")

    # Safety check: if config is a string, parse it to a dict
    if isinstance(config, str):
        config = json.loads(config)

    if not config or not config.get("enabled"):
        return

    # 2. Select Environment URL
    url = config.get("sandbox_url") if config.get("is_sandbox") else config.get("production_url")

    # 3. Build the Payload
    # Using doc.net_total and the difference for taxes ensures math matches Grand Total
    payload = {
        "POSID": int(config.get("pos_id")),
        "USIN": doc.name,
        "DateTime": f"{doc.posting_date} {doc.posting_time}",
        "BuyerName": doc.customer_name or "Guest",
        "BuyerNTN": doc.tax_id or "0000000-0",
        "TotalBillAmount": round(doc.grand_total, 2),
        "TotalQuantity": doc.total_qty,
        "TotalSaleValue": round(doc.net_total, 2),
        "TotalTaxCharged": round(doc.grand_total - doc.net_total, 2),
        "PaymentMode": 1,
        "InvoiceType": 1,
        "Items": []
    }

    for item in doc.items:
        # 1. Fetch PCT Code from Item Master
        pct = frappe.db.get_value("Item", item.item_code, "pct_code") or "1905.9000"

        # 2. Calculate Tax Amount per item
        # ERPNext stores 'net_amount' (before tax) and 'base_net_amount'.
        # The tax for this specific row is (amount - net_amount)
        tax_amount_per_item = round(item.amount - item.net_amount, 2)

        # 3. Calculate Tax Rate (%)
        # Formula: (Tax Amount / Net Amount) * 100
        item_tax_rate = 0
        if item.net_amount > 0:
            item_tax_rate = round((tax_amount_per_item / item.net_amount) * 100, 2)

        # Fallback for 0 tax items: check the first tax row if it exists
        if not item_tax_rate and doc.taxes:
            item_tax_rate = doc.taxes.rate

        payload["Items"].append({
            "ItemCode": item.item_code,
            "ItemName": item.item_name,
            "PCTCode": pct,
            "Quantity": abs(item.qty),
            "TaxRate": item_tax_rate,
            "SaleValue": round(item.net_amount, 2), # FBR wants SaleValue (Pre-tax)
            "TaxCharged": tax_amount_per_item,
            "TotalAmount": round(item.amount, 2), # Row total (Post-tax)
            "InvoiceType": 1
        })

    headers = {
        'Authorization': f'Bearer {config.get("access_code")}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)

        # 4. SAFE PARSING: This prevents the 'str' object error
        try:
            res_data = response.json()
        except (ValueError, TypeError, json.JSONDecodeError):
            res_data = {}

        if response.status_code == 200 and isinstance(res_data, dict):
            if res_data.get("InvoiceNumber"):
                doc.db_set("fbr_invoice_number", res_data.get("InvoiceNumber"))
                doc.db_set("fbr_qr_code", res_data.get("QR_Code_Value"))
                doc.db_set("fbr_sync_status", "Synced")
            else:
                doc.db_set("fbr_sync_status", "Failed")
                frappe.log_error(f"FBR Logic Error: {response.text}", "FBR Integration")
        else:
            doc.db_set("fbr_sync_status", "Failed")
            # If it's not a dict, log the raw text (could be an HTML error page)
            error_log = res_data if isinstance(res_data, str) else response.text
            frappe.log_error(f"FBR API Error {response.status_code}: {error_log}", "FBR Integration")

    except Exception:
        doc.db_set("fbr_sync_status", "Failed")
        frappe.log_error(frappe.get_traceback(), "FBR Connection Failed")