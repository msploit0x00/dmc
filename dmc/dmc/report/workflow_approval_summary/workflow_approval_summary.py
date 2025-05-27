# import frappe
# from frappe.utils import getdate


# def execute(filters=None):
#     filters = filters or {}

#     conditions = []
#     values = {}

#     if filters.get("reference_type"):
#         conditions.append("reference_type = %(reference_type)s")
#         values["reference_type"] = filters["reference_type"]

#     if filters.get("workflow_state"):
#         conditions.append("workflow_state = %(workflow_state)s")
#         values["workflow_state"] = filters["workflow_state"]

#     if filters.get("from_date"):
#         conditions.append("DATE(action_timestamp) >= %(from_date)s")
#         values["from_date"] = filters["from_date"]

#     if filters.get("to_date"):
#         conditions.append("DATE(action_timestamp) <= %(to_date)s")
#         values["to_date"] = filters["to_date"]

#     condition_str = " AND ".join(conditions)
#     if condition_str:
#         condition_str = "WHERE " + condition_str

#     data = frappe.db.sql(f"""
#         SELECT
#             reference_type,
#             reference_name,
#             action_by,
#             workflow_state,
#             action,
#             action_timestamp
#         FROM
#             `tabWorkflow Action Log`
#         {condition_str}
#         ORDER BY action_timestamp DESC
#     """, values, as_dict=True)

#     columns = [
#         {"label": "Reference Type", "fieldname": "reference_type",
#             "fieldtype": "Data", "width": 150},
#         {"label": "Reference Name", "fieldname": "reference_name",
#             "fieldtype": "Dynamic Link", "options": "reference_type", "width": 200},
#         {"label": "Action By", "fieldname": "action_by",
#             "fieldtype": "Link", "options": "User", "width": 150},
#         {"label": "Workflow State", "fieldname": "workflow_state",
#             "fieldtype": "Data", "width": 180},
#         {"label": "Action", "fieldname": "action",
#             "fieldtype": "Data", "width": 120},
#         {"label": "Action Timestamp", "fieldname": "action_timestamp",
#             "fieldtype": "Datetime", "width": 180},
#     ]

#     return columns, data


# import frappe
# import datetime


# def execute(filters=None):
#     filters = filters or {}

#     conditions = []
#     values = {}

#     if filters.get("reference_type"):
#         conditions.append("reference_type = %(reference_type)s")
#         values["reference_type"] = filters["reference_type"]

#     if filters.get("workflow_state"):
#         conditions.append("workflow_state = %(workflow_state)s")
#         values["workflow_state"] = filters["workflow_state"]

#     if filters.get("from_date"):
#         conditions.append("DATE(action_timestamp) >= %(from_date)s")
#         values["from_date"] = filters["from_date"]

#     if filters.get("to_date"):
#         conditions.append("DATE(action_timestamp) <= %(to_date)s")
#         values["to_date"] = filters["to_date"]

#     where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

#     raw_data = frappe.db.sql(f"""
#         SELECT
#             reference_name,
#             reference_type,
#             action_by,
#             workflow_state,
#             action_timestamp
#         FROM
#             `tabWorkflow Action Log`
#         {where_clause}
#         ORDER BY action_timestamp DESC
#     """, values, as_dict=True)

#     # Unique document references to be used as horizontal columns
#     reference_names = sorted(set([d["reference_name"] for d in raw_data]))

#     # Fields to be shown as rows (transposed)
#     field_labels = {
#         "reference_type": "Reference Type",
#         "action_by": "Action By",
#         "workflow_state": "Workflow State",
#         "action_timestamp": "Action Timestamp"
#     }

#     data = []
#     for fieldname, label in field_labels.items():
#         row = {"field": label}
#         for ref in reference_names:
#             matched = next(
#                 (d for d in raw_data if d["reference_name"] == ref), {})
#             value = matched.get(fieldname, "")
#             if isinstance(value, datetime.datetime):
#                 value = value.strftime("%d-%m-%Y %H:%M:%S")  # Format datetime
#             row[ref] = value
#         data.append(row)

#     # First column is the field name, rest are dynamic columns per document
#     columns = [{"label": "Field", "fieldname": "field",
#                 "fieldtype": "Data", "width": 180}]
#     for ref in reference_names:
#         columns.append({
#             "label": ref,
#             "fieldname": ref,
#             "fieldtype": "Data",
#             "width": 200
#         })

#     return columns, data


import frappe
import datetime


def execute(filters=None):
    filters = filters or {}

    conditions = []
    values = {}

    if filters.get("reference_type"):
        conditions.append("reference_type = %(reference_type)s")
        values["reference_type"] = filters["reference_type"]

    if filters.get("from_date"):
        conditions.append("DATE(action_timestamp) >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("DATE(action_timestamp) <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Fetch raw data
    raw_data = frappe.db.sql(f"""
        SELECT
            reference_name,
            workflow_state,
            action_by,
            action_timestamp
        FROM
            `tabWorkflow Action Log`
        {where_clause}
        ORDER BY action_timestamp DESC
    """, values, as_dict=True)

    # Collect unique reference names and workflow states
    reference_names = sorted(set(d["reference_name"] for d in raw_data))
    workflow_states = sorted(set(d["workflow_state"] for d in raw_data))

    # Prepare columns (workflow states as columns)
    columns = [{"label": "Document", "fieldname": "reference_name",
                "fieldtype": "Data", "width": 250}]
    for state in workflow_states:
        columns.append({
            "label": state,
            "fieldname": state,
            "fieldtype": "Data",
            "width": 250
        })

    # Build rows: one row per reference name
    data = []
    for ref in reference_names:
        row = {"reference_name": ref}
        ref_data = [d for d in raw_data if d["reference_name"] == ref]

        for state in workflow_states:
            entry = next(
                (d for d in ref_data if d["workflow_state"] == state), None)
            if entry:
                timestamp = entry["action_timestamp"].strftime(
                    "%d-%m-%Y %H:%M:%S")
                # row[state] = f"{entry['action_by']}\n{timestamp}"
                row[state] = f"👤 {entry['action_by']}\n🕒 {timestamp}"

            else:
                row[state] = ""
        data.append(row)

    return columns, data
