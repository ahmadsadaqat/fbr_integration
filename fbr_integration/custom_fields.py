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
                "options": "\nPending\nSynced\nFailed",
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
        ]
    }
    create_custom_fields(custom_fields)