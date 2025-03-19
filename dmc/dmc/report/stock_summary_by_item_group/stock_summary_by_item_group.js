
// frappe.query_reports["Stock Summary By Item Group"] = {
//     "filters": [
//         {
//             "fieldname": "warehouse",
//             "label": __("Warehouse"),
//             "fieldtype": "Link",
//             "options": "Warehouse",
//             "reqd": 1
//         }
//     ],
//     "formatter": function(value, row, column, data, default_formatter) {
//         if (column.fieldname === "item_group" && value.startsWith("<b>")) {
//             return `<strong>${value.replace(/<\/?b>/g, '')}</strong>`;
//         }
//         return default_formatter(value, row, column, data);
//     }
// };


frappe.query_reports["Stock Summary By Item Group"] = {
    "filters": [
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "reqd": 1
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        if (column.fieldname === "item_group" && value.startsWith("<b>")) {
            return `<strong>${value.replace(/<\/?b>/g, '')}</strong>`;
        }
        return default_formatter(value, row, column, data);
    }
};