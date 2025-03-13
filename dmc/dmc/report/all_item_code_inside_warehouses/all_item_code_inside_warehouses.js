frappe.query_reports["All Item Code Inside warehouses"] = {
    "filters": [
        {
            "fieldname": "item_group",
            "label": __("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 200
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 200,
            "on_change": function(report) {
                // Refresh the report when the warehouse filter changes
                report.refresh();
            }
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_days(frappe.datetime.now_date(), -30), // Default to last 30 days
            "reqd": 1 // Make it required
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.now_date(), // Default to today
            "reqd": 1 // Make it required
        }
    ]
};





// frappe.query_reports["All Item Code Inside warehouses"] = {
//     "filters": [
//         {
//             "fieldname": "item_group",
//             "label": __("Item Group"),
//             "fieldtype": "Link",
//             "options": "Item Group",
//             "width": 200
//         },
//         {
//             "fieldname": "warehouse",
//             "label": __("Warehouse"),
//             "fieldtype": "Link",
//             "options": "Warehouse",
//             "width": 200,
//             "on_change": function(report) {
//                 // Refresh the report when the warehouse filter changes
//                 report.refresh();
//             }
//         }
//     ]
// };