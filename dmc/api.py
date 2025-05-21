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
