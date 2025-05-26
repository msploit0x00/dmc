import frappe


def execute(filters=None):
    filters = filters or {}

    conditions = []
    values = {}

    if filters.get("reference_type"):
        conditions.append("reference_type = %(reference_type)s")
        values["reference_type"] = filters["reference_type"]

    if filters.get("workflow_state"):
        conditions.append("workflow_state = %(workflow_state)s")
        values["workflow_state"] = filters["workflow_state"]

    if filters.get("from_date"):
        conditions.append("DATE(action_timestamp) >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("DATE(action_timestamp) <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    data = frappe.db.sql(f"""
        SELECT
            reference_type,
            reference_name,
            action_by,
            workflow_state,
            action,
            action_timestamp
        FROM
            `tabWorkflow Action Log`
        {where_clause}
        ORDER BY action_timestamp DESC
    """, values, as_dict=True)

    columns = [
        {"label": "Reference Type", "fieldname": "reference_type",
            "fieldtype": "Data", "width": 150},
        {"label": "Reference Name", "fieldname": "reference_name",
            "fieldtype": "Dynamic Link", "options": "reference_type", "width": 200},
        {"label": "Action By", "fieldname": "action_by",
            "fieldtype": "Link", "options": "User", "width": 150},
        {"label": "Workflow State", "fieldname": "workflow_state",
            "fieldtype": "Data", "width": 180},
        {"label": "Action", "fieldname": "action",
            "fieldtype": "Data", "width": 120},
        {"label": "Action Timestamp", "fieldname": "action_timestamp",
            "fieldtype": "Datetime", "width": 180},
    ]

    return columns, data
