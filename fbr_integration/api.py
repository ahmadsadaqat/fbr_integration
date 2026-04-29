import frappe
import requests
import json
from frappe import _
from frappe.utils.background_jobs import enqueue

def queue_fbr_sync(doc, method=None):
    """Triggered on Sales Invoice Submit. Creates the log and queues the job."""

    # 1. Global Check
    config = frappe.conf.get("fbr_config")
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except:
            config = {}

    if not config or not config.get("enabled"):
        return

    # 2. Branch/Profile Specific Check
    fbr_enabled_in_profile = frappe.db.get_value("POS Profile", doc.pos_profile, "fbr_enabled")
    if not fbr_enabled_in_profile:
        return

    # 3. Create the Offline Sync Log entry
    log_exists = frappe.db.exists("Offline Sync Log", {"sales_invoice": doc.name}) or \
                 frappe.db.exists("Offline Sync Log", {"pos_invoice": doc.name})
    if not log_exists:
        log_data = {
            "doctype": "Offline Sync Log",
            "sync_status": "Pending",
            # Fetch additional info for the log fields
            "pos_profile": doc.pos_profile,
            "branch": doc.get("branch"),
            "customer": doc.customer,
            "grand_total": doc.grand_total
        }
        
        if doc.doctype == "Sales Invoice":
            log_data["sales_invoice"] = doc.name
        elif doc.doctype == "POS Invoice":
            log_data["pos_invoice"] = doc.name

        log = frappe.get_doc(log_data)

        # ignore_links=True is critical to bypass potential 'Alraheem' link errors
        log.insert(ignore_permissions=True, ignore_links=True)

        # Update Invoice status
        doc.db_set("fbr_sync_status", "Pending")

        # 4. Move the actual API call to a background worker
        # Path updated to use the correctly spelled folder 'fbr_integration'
        enqueue(
            "fbr_integration.api.process_fbr_sync",
            queue="short",
            timeout=300,
            log_name=log.name
        )

def process_fbr_sync(log_name):
    """Background worker that performs the actual FBR API call."""
    if not frappe.db.exists("Offline Sync Log", log_name):
        return

    log = frappe.get_doc("Offline Sync Log", log_name)
    log.db_set("sync_status", "Queued")

    # Load the invoice data
    if log.sales_invoice:
        doc = frappe.get_doc("Sales Invoice", log.sales_invoice)
    elif log.get("pos_invoice"):
        doc = frappe.get_doc("POS Invoice", log.pos_invoice)
    else:
        log.db_set("sync_status", "Failed")
        log.db_set("fbr_response", "Error: No linked Sales Invoice or POS Invoice found.")
        return
    config = frappe.conf.get("fbr_config")

    if isinstance(config, str):
        config = json.loads(config)

    # 1. Get POS ID from Profile, fallback to site_config
    pos_profile_id = frappe.db.get_value("POS Profile", doc.pos_profile, "fbr_pos_id")
    fbr_pos_id = pos_profile_id or config.get("pos_id")

    if not fbr_pos_id:
        log.db_set("sync_status", "Failed")
        log.db_set("fbr_response", "Error: No FBR POS ID found in POS Profile or site_config.")
        return

    # 2. Select Environment URL
    url = config.get("sandbox_url") if config.get("is_sandbox") else config.get("production_url")

    # 3. Build Payload
    payload = {
        "POSID": int(fbr_pos_id),
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
        pct = frappe.db.get_value("Item", item.item_code, "pct_code") or "1905.9000"
        tax_amt = round(item.amount - item.net_amount, 2)

        payload["Items"].append({
            "ItemCode": item.item_code,
            "ItemName": item.item_name,
            "PCTCode": pct,
            "Quantity": abs(item.qty),
            "TaxRate": round((tax_amt / item.net_amount * 100), 2) if item.net_amount else 0,
            "SaleValue": round(item.net_amount, 2),
            "TaxCharged": tax_amt,
            "TotalAmount": round(item.amount, 2),
            "InvoiceType": 1
        })

    headers = {
        'Authorization': f'Bearer {config.get("access_code")}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)

        # --- SAFE PARSING LOGIC ---
        res_data = {}
        is_json = True
        try:
            res_data = response.json()
        except (ValueError, json.JSONDecodeError):
            is_json = False
            res_data = {"raw_response": response.text}

        if response.status_code == 200 and is_json and isinstance(res_data, dict):
            inv_num = res_data.get("InvoiceNumber")

            if inv_num:
                # SUCCESS
                doc.db_set("fbr_invoice_number", inv_num)
                doc.db_set("fbr_qr_code", res_data.get("QR_Code_Value"))
                doc.db_set("fbr_sync_status", "Synced")

                log.db_set("fbr_invoice_number", inv_num)
                log.db_set("sync_status", "Synced")
                log.db_set("fbr_response", json.dumps(res_data, indent=4))
            else:
                # FBR rejected the data but sent JSON (Validation Error)
                doc.db_set("fbr_sync_status", "Failed")
                log.db_set("sync_status", "Failed")
                log.db_set("fbr_response", json.dumps(res_data, indent=4))
        else:
            # FBR sent an Error Page (HTML) or Non-200 Status
            doc.db_set("fbr_sync_status", "Failed")
            log.db_set("sync_status", "Failed")
            error_details = f"HTTP {response.status_code}\n\n{response.text}"
            log.db_set("fbr_response", error_details)

    except Exception as e:
        # Connection Timeout or System Error
        doc.db_set("fbr_sync_status", "Failed")
        log.db_set("sync_status", "Failed")
        log.db_set("fbr_response", frappe.get_traceback())