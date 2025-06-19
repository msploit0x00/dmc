frappe.query_reports["Custom Salary Register"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "currency",
            "label": __("Currency"),
            "fieldtype": "Link",
            "options": "Currency"
        },
        {
            "fieldname": "employee",
            "label": __("Employee"),
            "fieldtype": "Link",
            "options": "Employee"
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1
        },
        {
            "fieldname": "docstatus",
            "label": __("Document Status"),
            "fieldtype": "Select",
            "options": "Draft\nSubmitted\nCancelled",
            "default": "Submitted"
        }
    ]
}; 