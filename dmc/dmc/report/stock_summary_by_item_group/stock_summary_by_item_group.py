# import frappe

# def execute(filters=None):
#     if not filters:
#         filters = {}

#     warehouse = filters.get("warehouse")

#     if not warehouse:
#         frappe.throw("Please select a Warehouse.")

#     # Fetching the data
#     data = frappe.db.sql("""
#         SELECT 
#             i.item_group AS item_group,
#             i.item_name AS item_name,
#             SUM(sle.actual_qty) AS total_qty
#         FROM 
#             `tabStock Ledger Entry` sle
#         JOIN 
#             `tabItem` i ON sle.item_code = i.name
#         WHERE 
#             sle.warehouse = %s
#         GROUP BY 
#             i.item_group, i.item_name
#         ORDER BY 
#             i.item_group, i.item_name
#     """, (warehouse,), as_dict=True)

#     # Defining columns
#     columns = [
#         {"label": "Item (Grouped by Item Group)", "fieldname": "item_group", "fieldtype": "Data", "width": 300},
#         {"label": "Total Quantity", "fieldname": "total_qty", "fieldtype": "Float", "width": 150}
#     ]

#     formatted_data = []
#     current_group = None
#     group_total = 0

#     for row in data:
#         if row["item_group"] != current_group:
#             # Before switching groups, store the total row with "Total Balance Quantity Of"
#             if current_group:
#                 formatted_data.append({"item_group": f"<b>Total Balance Quantity Of {current_group}</b>", "total_qty": group_total})
            
#             current_group = row["item_group"]
#             group_total = 0

#         # Add item under its group
#         formatted_data.append({"item_group": f"- {row['item_name']}", "total_qty": row["total_qty"]})
#         group_total += row["total_qty"]

#     # Add the last group total
#     if current_group:
#         formatted_data.append({"item_group": f"<b>Total Balance Quantity Of {current_group}</b>", "total_qty": group_total})

#     return columns, formatted_data





import frappe
def execute(filters=None):
    if not filters:
        filters = {}
    warehouse = filters.get("warehouse")
    to_date = filters.get("to_date")
    if not warehouse:
        frappe.throw("Please select a Warehouse.")
    if not to_date:
        frappe.throw("Please select a To Date.")
    # Fetching the data with only the To Date filter
    data = frappe.db.sql("""
        SELECT 
            i.item_group AS item_group,
            i.item_name AS item_name,
            SUM(sle.actual_qty) AS total_qty
        FROM 
            `tabStock Ledger Entry` sle
        JOIN 
            `tabItem` i ON sle.item_code = i.name
        WHERE 
            sle.warehouse = %s
            AND sle.posting_datetime <= %s
        GROUP BY 
            i.item_group, i.item_name
        ORDER BY 
            i.item_group, i.item_name
    """, (warehouse, to_date), as_dict=True)
    # Defining columns
    columns = [
        {"label": "Item (Grouped by Item Group)", "fieldname": "item_group", "fieldtype": "Data", "width": 300},
        {"label": "Total Quantity", "fieldname": "total_qty", "fieldtype": "Float", "width": 150, "precision": 1}
    ]
    formatted_data = []
    current_group = None
    group_total = 0
    for row in data:
        if row["item_group"] != current_group:
            if current_group:
                formatted_data.append({"item_group": f"<b>Total Balance Quantity: {current_group}</b>", "total_qty": group_total})
            current_group = row["item_group"]
            group_total = 0
        formatted_data.append({"item_group": f"- {row['item_name']}", "total_qty": row["total_qty"]})
        group_total += row["total_qty"]
    if current_group:
        formatted_data.append({"item_group": f"<b>Total Balance Quantity Of {current_group}</b>", "total_qty": group_total})
    return columns, formatted_data