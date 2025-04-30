frappe.query_reports["Target Report"] = {
    filters: [
        {
            fieldname: "sales_person",
            label: __("Sales Person"),
            fieldtype: "Link",
            options: "Sales Person"
        },
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer"
        },
        {
            fieldname: "customer_address",
            label: __("Customer Address"),
            fieldtype: "Link",
            options: "Address"
        },
        {
            fieldname: "custom_customer_type",
            label: __("Customer Type"),
            fieldtype: "Select",
            options: ["", "UPA", "Private", "MOH"]
        },
        
        {
            fieldname: "custom_item_department",
            label: __("Item Department"),
            fieldtype: "Select",
            options: [
                "",
                "Cardio",
                "Infection",
                "Peripheral",
                "Radiology",
                "Wound Care",
                "NeuSoft"
            ],
        },
        {
            fieldname: "fiscal_year",
            label: __("Fiscal Year"),
            fieldtype: "Link",
            options: "Fiscal Year"
        },
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            options: [
                "",
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ],
            default: ""
        }
    ]
};
