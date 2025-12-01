import frappe
from frappe import _
from frappe.utils import flt

import erpnext

salary_slip = frappe.qb.DocType("Salary Slip")
salary_detail = frappe.qb.DocType("Salary Detail")
salary_component = frappe.qb.DocType("Salary Component")


def execute(filters=None):
    if not filters:
        filters = {}

    currency = None
    if filters.get("currency"):
        currency = filters.get("currency")
    company_currency = erpnext.get_company_currency(filters.get("company"))

    salary_slips = get_salary_slips(filters, company_currency)
    if not salary_slips:
        return [], []

    # Get ALL salary components from master, not just from salary slips
    earning_types, ded_types = get_all_earning_and_deduction_types()
    columns = get_columns(earning_types, ded_types)

    ss_earning_map = get_salary_slip_details(
        salary_slips, currency, company_currency, "earnings")
    ss_ded_map = get_salary_slip_details(
        salary_slips, currency, company_currency, "deductions")

    doj_map = get_employee_doj_map()

    data = []
    for ss in salary_slips:
        row = {
            "salary_slip_id": ss.name,
            "employee": ss.employee,
            "employee_name": ss.employee_name,
            "data_of_joining": doj_map.get(ss.employee),
            "branch": ss.branch,
            "department": ss.department,
            "designation": ss.designation,
            "company": ss.company,
            "start_date": ss.start_date,
            "end_date": ss.end_date,
            "leave_without_pay": ss.leave_without_pay,
            "absent_days": ss.absent_days,
            "payment_days": ss.payment_days,
            "currency": currency or company_currency,
            "total_loan_repayment": ss.total_loan_repayment,
        }

        update_column_width(ss, columns)

        # Add all earning components (will be 0 if not in this salary slip)
        for e in earning_types:
            row.update(
                {frappe.scrub(e): ss_earning_map.get(ss.name, {}).get(e, 0.0)})

        # Add all deduction components (will be 0 if not in this salary slip)
        for d in ded_types:
            row.update(
                {frappe.scrub(d): ss_ded_map.get(ss.name, {}).get(d, 0.0)})

        # Calculate Total Salary using all possible keys
        basic_keys = ["Basic"]
        commission_keys = ["Commission", "Commision"]
        car_allowance_keys = ["Car Allowance"]
        transportation_allowance_keys = ["Transportation Allowance"]
        phone_allowance_keys = ["Phone Allowance"]

        total_salary = (
            get_component_total(ss_earning_map, ss.name, basic_keys) +
            get_component_total(ss_earning_map, ss.name, commission_keys) +
            get_component_total(ss_earning_map, ss.name, car_allowance_keys) +
            get_component_total(ss_earning_map, ss.name, transportation_allowance_keys) +
            get_component_total(ss_earning_map, ss.name, phone_allowance_keys)
        )
        row.update({"total_salary": total_salary})

        if currency == company_currency:
            row.update(
                {
                    "gross_pay": flt(ss.gross_pay) * flt(ss.exchange_rate),
                    "total_deduction": flt(ss.total_deduction) * flt(ss.exchange_rate),
                    "net_pay": flt(ss.net_pay) * flt(ss.exchange_rate),
                }
            )
        else:
            row.update(
                {"gross_pay": ss.gross_pay,
                    "total_deduction": ss.total_deduction, "net_pay": ss.net_pay}
            )

        data.append(row)

    return columns, data


def get_columns(earning_types, ded_types):
    columns = [
        {
            "label": _("Salary Slip ID"),
            "fieldname": "salary_slip_id",
            "fieldtype": "Link",
            "options": "Salary Slip",
            "width": 150,
        },
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 120,
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "label": _("Date of Joining"),
            "fieldname": "data_of_joining",
            "fieldtype": "Date",
            "width": 80,
        },
        {
            "label": _("Branch"),
            "fieldname": "branch",
            "fieldtype": "Link",
            "options": "Branch",
            "width": -1,
        },
        {
            "label": _("Department"),
            "fieldname": "department",
            "fieldtype": "Link",
            "options": "Department",
            "width": -1,
        },
        {
            "label": _("Designation"),
            "fieldname": "designation",
            "fieldtype": "Link",
            "options": "Designation",
            "width": 120,
        },
        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 120,
        },
        {
            "label": _("Start Date"),
            "fieldname": "start_date",
            "fieldtype": "Data",
            "width": 80,
        },
        {
            "label": _("End Date"),
            "fieldname": "end_date",
            "fieldtype": "Data",
            "width": 80,
        },
        {
            "label": _("Leave Without Pay"),
            "fieldname": "leave_without_pay",
            "fieldtype": "Float",
            "width": 50,
        },
        {
            "label": _("Absent Days"),
            "fieldname": "absent_days",
            "fieldtype": "Float",
            "width": 50,
        },
        {
            "label": _("Payment Days"),
            "fieldname": "payment_days",
            "fieldtype": "Float",
            "width": 120,
        },
    ]

    for earning in earning_types:
        columns.append(
            {
                "label": earning,
                "fieldname": frappe.scrub(earning),
                "fieldtype": "Currency",
                "options": "currency",
                "width": 120,
            }
        )

    # Add Total Salary column after Phone Allowance
    columns.append(
        {
            "label": _("Total Salary"),
            "fieldname": "total_salary",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        }
    )

    columns.append(
        {
            "label": _("Gross Pay"),
            "fieldname": "gross_pay",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        }
    )

    for deduction in ded_types:
        columns.append(
            {
                "label": deduction,
                "fieldname": frappe.scrub(deduction),
                "fieldtype": "Currency",
                "options": "currency",
                "width": 120,
            }
        )

    columns.extend(
        [
            {
                "label": _("Loan Repayment"),
                "fieldname": "total_loan_repayment",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 120,
            },
            {
                "label": _("Total Deduction"),
                "fieldname": "total_deduction",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 120,
            },
            {
                "label": _("Net Pay"),
                "fieldname": "net_pay",
                "fieldtype": "Currency",
                "options": "currency",
                "width": 120,
            },
            {
                "label": _("Currency"),
                "fieldtype": "Data",
                "fieldname": "currency",
                "width": 80,
            },
        ]
    )

    return columns


# def get_all_earning_and_deduction_types():
#     """
#     Get ALL enabled salary components from Salary Component master,
#     not just those present in the current salary slips
#     """
#     earning_types = []
#     deduction_types = []

#     # Fetch all enabled salary components
#     salary_components = frappe.get_all(
#         "Salary Component",
#         filters={"disabled": 0},
#         fields=["salary_component", "type"],
#         order_by="salary_component"
#     )

#     for component in salary_components:
#         if component.type == "Earning":
#             earning_types.append(component.salary_component)
#         elif component.type == "Deduction":
#             deduction_types.append(component.salary_component)

#     return earning_types, deduction_types

def get_all_earning_and_deduction_types():
    """
    Get ALL enabled salary components sorted by custom_display_order
    """
    # استخدام SQL مباشر عشان نضمن الترتيب صح
    components = frappe.db.sql("""
        SELECT 
            salary_component, 
            type,
            IFNULL(custom_display_order, 999999) as display_order
        FROM `tabSalary Component`
        WHERE disabled = 0
        ORDER BY display_order ASC, salary_component ASC
    """, as_dict=1)

    earning_types = []
    deduction_types = []

    for component in components:
        if component.type == "Earning":
            earning_types.append(component.salary_component)
        elif component.type == "Deduction":
            deduction_types.append(component.salary_component)

    return earning_types, deduction_types


def get_earning_and_deduction_types(salary_slips):
    """
    OLD FUNCTION - Get only components that exist in current salary slips
    Keeping this for reference but not using it anymore
    """
    salary_component_and_type = {_("Earning"): [], _("Deduction"): []}

    for salary_component in get_salary_components(salary_slips):
        component_type = get_salary_component_type(salary_component)
        salary_component_and_type[_(component_type)].append(salary_component)

    return sorted(salary_component_and_type[_("Earning")]), sorted(salary_component_and_type[_("Deduction")])


def update_column_width(ss, columns):
    if ss.branch is not None:
        columns[3].update({"width": 120})
    if ss.department is not None:
        columns[4].update({"width": 120})
    if ss.designation is not None:
        columns[5].update({"width": 120})
    if ss.leave_without_pay is not None:
        columns[9].update({"width": 120})


def get_salary_components(salary_slips):
    salary_components = set()
    for salary_slip in salary_slips:
        for component in frappe.get_all(
            "Salary Detail",
            filters={"parent": salary_slip.name},
            fields=["salary_component"],
        ):
            salary_components.add(component.salary_component)
    return salary_components


def get_salary_component_type(salary_component):
    return frappe.get_cached_value("Salary Component", salary_component, "type")


def get_salary_slips(filters, company_currency):
    doc_status = {"Draft": 0, "Submitted": 1, "Cancelled": 2}

    query = frappe.qb.from_(salary_slip).select(
        salary_slip.star
    ).where(
        (salary_slip.docstatus == doc_status[filters.get("docstatus")])
        & (salary_slip.start_date >= filters.get("from_date"))
        & (salary_slip.end_date <= filters.get("to_date"))
    )

    if filters.get("company"):
        query = query.where(salary_slip.company == filters.get("company"))

    if filters.get("employee"):
        query = query.where(salary_slip.employee == filters.get("employee"))

    if filters.get("currency") and filters.get("currency") != company_currency:
        query = query.where(salary_slip.currency == filters.get("currency"))

    salary_slips = query.run(as_dict=1)
    return salary_slips


def get_employee_doj_map():
    return frappe._dict(
        frappe.get_all(
            "Employee",
            fields=["name", "date_of_joining"],
            as_list=1,
        )
    )


def get_salary_slip_details(salary_slips, currency, company_currency, component_type):
    salary_slips = [ss.name for ss in salary_slips]

    result = frappe._dict()
    for d in frappe.get_all(
        "Salary Detail",
        filters={
            "parent": ("in", salary_slips),
            "parentfield": component_type,
        },
        fields=["parent", "salary_component", "amount", "default_amount"],
    ):
        result.setdefault(d.parent, frappe._dict()).setdefault(
            d.salary_component, 0.0)
        if currency == company_currency:
            result[d.parent][d.salary_component] += flt(d.amount) * flt(
                frappe.get_cached_value(
                    "Salary Slip", d.parent, "exchange_rate")
            )
        else:
            result[d.parent][d.salary_component] += flt(d.amount)

    return result


def get_component_total(earning_map, ss_name, keys):
    return sum(flt(earning_map.get(ss_name, {}).get(k, 0)) for k in keys)
