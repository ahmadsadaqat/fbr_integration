import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def setup_custom_fields():
    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "fbr_invoice_number",
                "label": "FBR Invoice Number",
                "fieldtype": "Data",
                "read_only": 1,
                "insert_after": "status"
            },
            {
                "fieldname": "fbr_qr_code",
                "label": "FBR QR Code",
                "fieldtype": "Small Text",
                "hidden": 1
            },
            {
                "fieldname": "fbr_sync_status",
                "label": "FBR Sync Status",
                "fieldtype": "Select",
                "options": "\nPending\nQueued\nSynced\nFailed\nMalicious", # Added Queued and Malicious
                "default": "Pending",
                "read_only": 1
            }
        ],
        "POS Invoice": [
            {
                "fieldname": "fbr_invoice_number",
                "label": "FBR Invoice Number",
                "fieldtype": "Data",
                "read_only": 1,
                "insert_after": "status"
            },
            {
                "fieldname": "fbr_qr_code",
                "label": "FBR QR Code",
                "fieldtype": "Small Text",
                "hidden": 1
            },
            {
                "fieldname": "fbr_sync_status",
                "label": "FBR Sync Status",
                "fieldtype": "Select",
                "options": "\nPending\nQueued\nSynced\nFailed\nMalicious",
                "default": "Pending",
                "read_only": 1
            }
        ],
        "Item": [
            {
                "fieldname": "pct_code",
                "label": "FBR PCT Code",
                "fieldtype": "Data",
                "description": "Standard PCT Code for FBR (e.g., 1905.9000 for Bakers)",
                "insert_after": "item_group"
            }
        ],
        "POS Profile": [
            {
                "fieldname": "fbr_enabled",
                "label": "Enable FBR Integration",
                "fieldtype": "Check",
                "default": 0,
                "insert_after": "name"
            },
            {
                "fieldname": "fbr_pos_id",
                "label": "FBR POS ID",
                "fieldtype": "Data",
                "description": "Unique POS ID issued by FBR for this specific counter/branch",
                "insert_after": "name"
            }
        ]
    }
    create_custom_fields(custom_fields)