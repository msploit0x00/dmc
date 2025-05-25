# داخل dmc/dmc/report/items_received_with_batch_info/items_received_with_batch_info.py

import frappe
from frappe.utils import flt


def execute(filters=None):
    columns = [
        {"label": "Posting Date", "fieldname": "posting_date",
            "fieldtype": "Date", "width": 120},
        {"label": "Item Code", "fieldname": "item_code",
            "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": "Item Name", "fieldname": "item_name",
            "fieldtype": "Data", "width": 180},
        {"label": "Batch No", "fieldname": "batch_no",
            "fieldtype": "Link", "options": "Batch", "width": 130},
        {"label": "GTIN", "fieldname": "custom_gtin",
            "fieldtype": "Data", "width": 130},
        {"label": "Barcode", "fieldname": "barcode",
            "fieldtype": "Data", "width": 130},
    ]

    data = frappe.db.sql("""
        SELECT
            pr.posting_date,
            pri.item_code,
            i.item_name,
            pri.batch_no,
            b.custom_gtin,
            ib.barcode
        FROM
            `tabPurchase Receipt Item` pri
        JOIN
            `tabPurchase Receipt` pr ON pri.parent = pr.name
        LEFT JOIN
            `tabBatch` b ON b.name = pri.batch_no
        LEFT JOIN
            `tabItem` i ON i.name = pri.item_code
        LEFT JOIN
            `tabItem Barcode` ib ON ib.parent = pri.item_code
        WHERE
            pr.posting_date BETWEEN %(from_date)s AND %(to_date)s
        ORDER BY
            pr.posting_date DESC
    """, filters, as_dict=True)

    return columns, data
