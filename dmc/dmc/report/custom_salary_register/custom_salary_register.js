frappe.query_reports["Custom Salary Register"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company"),
            "reqd": 1
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "employee",
            "label": __("Employee"),
            "fieldtype": "Link",
            "options": "Employee"
        },
        {
            "fieldname": "currency",
            "label": __("Currency"),
            "fieldtype": "Link",
            "options": "Currency",
            "default": erpnext.get_currency(frappe.defaults.get_global_default("Company"))
        },
        {
            "fieldname": "docstatus",
            "label": __("Document Status"),
            "fieldtype": "Select",
            "options": ["Draft", "Submitted", "Cancelled"],
            "default": "Submitted"
        }
    ]
}; 