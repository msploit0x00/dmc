
import frappe
from frappe.utils import now_datetime


def log_workflow_action(doc, method):
    if doc.doctype == "Workflow Action Log":
        return  # Avoid recursion when logging the log itself
    print(f"Triggered for {doc.doctype} - {doc.name} - method: {method}")

    workflow = frappe.get_all("Workflow", filters={
                              "document_type": doc.doctype}, fields=["name", "workflow_state_field"])
    if not workflow:
        print("No Workflow found for this DocType.")
        return

    state_field = workflow[0].workflow_state_field
    if not state_field:
        print("No workflow_state_field defined in Workflow.")
        return

    workflow_state = doc.get(state_field)
    if not workflow_state:
        print(f"workflow_state_field '{state_field}' is empty.")
        return

    print(f"Logging: {workflow_state}")
    try:
        frappe.get_doc({
            "doctype": "Workflow Action Log",
            "reference_type": doc.doctype,
            "reference_name": doc.name,
            "action_by": frappe.session.user,
            "workflow_state": workflow_state,
            "action": method,
            "action_timestamp": now_datetime()
        }).insert(ignore_permissions=True)
        print("Log inserted.")
    except Exception as e:
        print(f"Error: {e}")
