import frappe


def execute(filters=None):
    filters = filters or {}
    conditions = []
    values = {}

    if filters.get("from_date"):
        conditions.append("batch.creation >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("batch.creation <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    data = frappe.db.sql(f"""
        SELECT
            batch.item AS item_code,
            item.item_name,
            batch.name AS batch_no,
            batch.custom_gtin AS gtin,
            batch.custom_full_barcode,
            batch.manufacturing_date,
            batch.expiry_date,
            batch.creation AS created_on
        FROM
            `tabBatch` batch
        LEFT JOIN
            `tabItem` item ON batch.item = item.name
        {where_clause}
        ORDER BY
            batch.creation DESC
    """, values, as_dict=True)

    columns = [
        {"label": "Item Code", "fieldname": "item_code",
            "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": "Item Name", "fieldname": "item_name",
            "fieldtype": "Data", "width": 180},
        {"label": "Batch No", "fieldname": "batch_no",
            "fieldtype": "Link", "options": "Batch", "width": 150},
        {"label": "GTIN", "fieldname": "gtin", "fieldtype": "Data", "width": 150},
        {"label": "Full Barcode", "fieldname": "custom_full_barcode",
            "fieldtype": "Data", "width": 150},
        {"label": "Manufacturing Date", "fieldname": "manufacturing_date",
            "fieldtype": "Date", "width": 120},
        {"label": "Expiry Date", "fieldname": "expiry_date",
            "fieldtype": "Date", "width": 120},
        {"label": "Created On", "fieldname": "created_on",
            "fieldtype": "Datetime", "width": 160},
    ]

    return columns, data
