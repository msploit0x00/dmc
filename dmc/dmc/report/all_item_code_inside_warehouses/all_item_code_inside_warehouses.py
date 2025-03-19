import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters=None):
    columns = [
        {
            "fieldname": "item_group",
            "label": _("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 200
        }
    ]
    
    warehouse_filter = filters.get("warehouse") if filters else None
    
    if warehouse_filter:
        columns.append({
            "fieldname": warehouse_filter,
            "label": _(warehouse_filter),
            "fieldtype": "Float",
            "width": 120
        })
    else:
        warehouses = frappe.get_all("Warehouse", fields=["name"])
        for warehouse in warehouses:
            columns.append({
                "fieldname": warehouse.name,
                "label": _(warehouse.name),
                "fieldtype": "Float",
                "width": 120
            })
    
    return columns

def get_data(filters=None):
    item_group_filter = filters.get("item_group") if filters else None
    warehouse_filter = filters.get("warehouse") if filters else None
    from_date = filters.get("from_date") if filters else None
    to_date = filters.get("to_date") if filters else None
    
    item_groups = frappe.get_all("Item Group", fields=["name"], filters={"name": item_group_filter} if item_group_filter else {})
    warehouses = frappe.get_all("Warehouse", fields=["name"], filters={"name": warehouse_filter} if warehouse_filter else {})
    
    data = []
    for item_group in item_groups:
        row = {"item_group": item_group.name}
        for warehouse in warehouses:
            conditions = ["item.item_group = %s", "sle.warehouse = %s"]
            values = [item_group.name, warehouse.name]

            # Add date range filter if provided
            if from_date:
                conditions.append("sle.posting_date >= %s")
                values.append(from_date)
            if to_date:
                conditions.append("sle.posting_date <= %s")
                values.append(to_date)

            actual_qty_sum = frappe.db.sql(f"""
                SELECT SUM(sle.actual_qty) as total_qty
                FROM `tabStock Ledger Entry` sle
                JOIN `tabItem` item ON sle.item_code = item.name
                WHERE {" AND ".join(conditions)}
            """, values, as_dict=True)[0].total_qty or 0  # Ensure sum is never None
            
            row[warehouse.name] = actual_qty_sum
        data.append(row)
    
    return data