frappe.query_reports["Custom Stock Ledger"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: function () {
				const company = frappe.query_report.get_filter_value("company");
				return { filters: { company: company } };
			},
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
			get_query: function () {
				return { query: "erpnext.controllers.queries.item_query" };
			},
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "batch_no",
			label: __("Batch No"),
			fieldtype: "Link",
			options: "Batch",
			on_change() {
				const batch_no = frappe.query_report.get_filter_value("batch_no");
				frappe.query_report.set_filter_value(
					"segregate_serial_batch_bundle",
					batch_no ? 1 : 0
				);
			},
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Link",
			options: "Brand",
		},
		{
			fieldname: "voucher_no",
			label: __("Voucher #"),
			fieldtype: "Data",
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
		},
		{
			fieldname: "include_uom",
			label: __("Include UOM"),
			fieldtype: "Link",
			options: "UOM",
		},
		{
			fieldname: "valuation_field_type",
			label: __("Valuation Field Type"),
			fieldtype: "Select",
			width: "80",
			options: "Currency\nFloat",
			default: "Currency",
		},
		{
			fieldname: "segregate_serial_batch_bundle",
			label: __("Segregate Serial / Batch Bundle"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "show_pivot_view",
			label: __("Show Pivot View"),
			fieldtype: "Check",
			default: 0,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname == "out_qty" && data && data.out_qty < 0) {
			value = `<span style="color:red;">${value}</span>`;
		} else if (column.fieldname == "in_qty" && data && data.in_qty > 0) {
			value = `<span style="color:green;">${value}</span>`;
		}
		return value;
	},

	// This runs every time report refreshes
	onload(report) {
		report.refresh_pivot_colors = () => {
			const pivot = document.querySelector(".pivot-table");
			if (!pivot) return;

			pivot.querySelectorAll("td").forEach((td) => {
				const text = td.innerText.trim().replace(/,/g, "");
				if (!text) return;

				const num = parseFloat(text);
				if (!isNaN(num)) {
					if (num < 0) {
						td.style.color = "red";
						if (!td.innerText.startsWith("-")) {
							td.innerText = "-" + td.innerText;
						}
					} else if (num > 0) {
						td.style.color = "green";
					}
				}
			});
		};

		// Recolor pivot after each refresh
		frappe.realtime.on("report-render-complete", () => {
			setTimeout(() => report.refresh_pivot_colors(), 300);
		});

		// Fallback observer if realtime event doesn’t fire
		const target = document.querySelector(".report-container");
		if (target) {
			const obs = new MutationObserver(() => report.refresh_pivot_colors());
			obs.observe(target, { childList: true, subtree: true });
		}
	},
};

erpnext.utils.add_inventory_dimensions("Stock Ledger", 10);
