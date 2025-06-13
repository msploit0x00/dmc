frappe.query_reports["Workflow Approval Summary"] = {
	filters: [
		{
			fieldname: "reference_type",
			label: "Document Type",
			fieldtype: "Link",
			options: "DocType",
			default: "Sales Order"
		},
		{
			fieldname: "workflow_state",
			label: "Workflow State",
			fieldtype: "Data"
		},
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: "To Date",
			fieldtype: "Date",
		}
	]
}
