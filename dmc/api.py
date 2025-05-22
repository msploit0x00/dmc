import frappe
from frappe import _


@frappe.whitelist()
def get_cost_center_allocation_naming_series(sales_person):
    employee = frappe.db.get_value("Sales Person", sales_person, "employee")
    if not employee:
        return

    department = frappe.db.get_value("Employee", employee, "department")
    if not department:
        return

    payroll_cost_center = frappe.db.get_value(
        "Department", department, "payroll_cost_center")
    if not payroll_cost_center:
        return

    cost_center_allocation = frappe.get_all(
        "Cost Center Allocation",
        filters={"cost_center": payroll_cost_center},
        fields=["name"]
    )

    return cost_center_allocation[0].name if cost_center_allocation else None


@frappe.whitelist()
def get_batch_and_gtin(item_code):
    batch = frappe.get_all(
        "Batch",
        filters={"item": item_code},
        fields=["name", "custom_gtin"],
        limit=1
    )

    if batch:
        return batch[0]
    return None
# @frappe.whitelist()
# def get_batch_info_for_item(item_code):
#     # Get the latest batch for the item
#     batch = frappe.get_all("Batch",
#                            filters={"item": item_code, "disabled": 0},
#                            fields=["name", "custom_gtin"],
#                            order_by="creation desc",
#                            limit=1
#                            )

#     if not batch:
#         return None

#     return {
#         "batch_no": batch[0].name,
#         "custom_gtin": batch[0].custom_gtin
#     }
