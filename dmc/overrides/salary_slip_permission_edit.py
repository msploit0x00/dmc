"""
Salary Slip Permissions - SIMPLE WORKING VERSION

This is the minimal code needed. User Permissions must be configured
separately to exclude Salary Slip doctype.
"""

import frappe
from frappe.permissions import get_roles


def salary_slip_permission_query_conditions(user):
    """
    Filter Salary Slips in list view
    """
    if user == "Administrator":
        return None

    user_roles = get_roles(user)

    # System Manager and Payroll see all
    if any(role in ["System Manager", "Payroll"] for role in user_roles):
        return None

    # Others see only their own
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

    if not employee:
        return "1=0"

    return f"`tabSalary Slip`.`employee` = '{employee}'"


def has_permission_salary_slip(doc, ptype="read", user=None):
    """
    Check permission for individual Salary Slip document
    """
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    user_roles = get_roles(user)

    # System Manager and Payroll see all
    if any(role in ["System Manager", "Payroll"] for role in user_roles):
        return True

    # Others see only their own
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

    if not employee:
        return False

    return doc.employee == employee
