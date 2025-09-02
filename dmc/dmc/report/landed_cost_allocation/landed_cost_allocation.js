// landed_cost_allocation.js - Fixed Version
frappe.query_reports["Landed Cost Allocation"] = {
	"filters": [
		{
			"fieldname": "item",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
			"width": "80"
		},
		{
			"fieldname": "shipment_name",
			"label": __("Shipment Name"),
			"fieldtype": "Link",
			"options": "Shipment Name",  // Fixed: Changed from "Data" to "Link" with "Shipment" options
			"width": "120"
		},
		{
			"fieldname": "landed_cost_name",
			"label": __("Landed Cost Name"),
			"fieldtype": "Link",
			"options": "Landed Cost Voucher",
			"width": "120"
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		}
	],

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		// Format shipment name as clickable link
		if (column.fieldname == "shipment_name" && data && data.shipment_name) {
			return `<a href="/app/shipment/${data.shipment_name}" target="_blank" style="color: #0078d4; text-decoration: underline;">${data.shipment_name}</a>`;
		}

		// Format currency columns
		if (["amount", "total_tax_amount", "item_tax_share", "total_landed_cost", "applicable_charges", "rate"].includes(column.fieldname)) {
			if (value && !isNaN(value)) {
				return format_currency(value);
			}
		}

		// Format percentage columns
		if (["item_percentage"].includes(column.fieldname)) {
			if (value && !isNaN(value)) {
				return `${parseFloat(value).toFixed(2)}%`;
			}
		}

		return value;
	},

	"onload": function (report) {
		// Add summary section
		report.page.add_inner_button(__("Show Summary"), function () {
			show_summary_dialog(report.data);
		});

		// Add export button
		report.page.add_inner_button(__("Export to Excel"), function () {
			export_to_excel(report.data, report.columns);
		});

		// Add validation button
		report.page.add_inner_button(__("Validate Totals"), function () {
			validate_report_totals(report.data);
		});

		// Add breakdown button for detailed analysis
		report.page.add_inner_button(__("Cost Breakdown"), function () {
			show_cost_breakdown(report.data);
		});
	}
};

// Helper functions
function format_currency(amount) {
	if (!amount) return "0.00";
	return new Intl.NumberFormat('en-US', {
		style: 'decimal',
		minimumFractionDigits: 2,
		maximumFractionDigits: 2
	}).format(amount);
}

function show_summary_dialog(data) {
	if (!data || data.length === 0) {
		frappe.msgprint(__("No data to summarize"));
		return;
	}

	// Calculate summary statistics
	let summary = calculate_summary(data);

	let html = `
        <div style="padding: 20px;">
            <h4>Landed Cost Summary</h4>
            <table class="table table-bordered">
                <tr>
                    <td><strong>Total Vouchers:</strong></td>
                    <td>${summary.total_vouchers}</td>
                </tr>
                <tr>
                    <td><strong>Total Shipments:</strong></td>
                    <td>${summary.total_shipments}</td>
                </tr>
                <tr>
                    <td><strong>Total Items:</strong></td>
                    <td>${summary.total_items}</td>
                </tr>
                <tr>
                    <td><strong>Total Item Amount:</strong></td>
                    <td>${format_currency(summary.total_amount)}</td>
                </tr>
                <tr>
                    <td><strong>Total Tax Amount:</strong></td>
                    <td>${format_currency(summary.total_taxes)}</td>
                </tr>
                <tr>
                    <td><strong>Total Applicable Charges:</strong></td>
                    <td>${format_currency(summary.total_applicable_charges)}</td>
                </tr>
                <tr>
                    <td><strong>Average Item Percentage:</strong></td>
                    <td>${summary.avg_item_percentage.toFixed(2)}%</td>
                </tr>
            </table>
        </div>
    `;

	frappe.msgprint({
		title: __("Summary"),
		message: html,
		wide: true
	});
}

function calculate_summary(data) {
	let vouchers = new Set();
	let shipments = new Set();
	let items = new Set();
	let total_amount = 0;
	let total_taxes = 0;
	let total_applicable_charges = 0;
	let total_item_percentage = 0;
	let percentage_count = 0;

	data.forEach(row => {
		vouchers.add(row.landed_cost_voucher);
		if (row.shipment_name) shipments.add(row.shipment_name);
		items.add(row.item_code);
		total_amount += (row.amount || 0);
		total_taxes += (row.item_tax_share || 0);

		// Only count applicable charges once per voucher
		if (!vouchers.has(row.landed_cost_voucher + '_counted')) {
			total_applicable_charges += (row.applicable_charges || 0);
			vouchers.add(row.landed_cost_voucher + '_counted');
		}

		if (row.item_percentage) {
			total_item_percentage += row.item_percentage;
			percentage_count++;
		}
	});

	return {
		total_vouchers: vouchers.size,
		total_shipments: shipments.size,
		total_items: items.size,
		total_amount: total_amount,
		total_taxes: total_taxes,
		total_applicable_charges: total_applicable_charges,
		avg_item_percentage: percentage_count > 0 ? total_item_percentage / percentage_count : 0
	};
}

function show_cost_breakdown(data) {
	if (!data || data.length === 0) {
		frappe.msgprint(__("No data available for breakdown"));
		return;
	}

	// Group data by voucher and item
	let breakdown = {};

	data.forEach(row => {
		let voucher = row.landed_cost_voucher;
		let item = row.item_code;

		if (!breakdown[voucher]) {
			breakdown[voucher] = {
				shipment: row.shipment_name,
				applicable_charges: row.applicable_charges,
				items: {}
			};
		}

		if (!breakdown[voucher].items[item]) {
			breakdown[voucher].items[item] = {
				item_name: row.item_name,
				amount: row.amount,
				percentage: row.item_percentage,
				taxes: [],
				total_tax_share: 0
			};
		}

		if (row.tax_description) {
			breakdown[voucher].items[item].taxes.push({
				description: row.tax_description,
				total_amount: row.total_tax_amount,
				item_share: row.item_tax_share
			});
			breakdown[voucher].items[item].total_tax_share += (row.item_tax_share || 0);
		}
	});

	let html = '<div style="padding: 20px;"><h4>Detailed Cost Breakdown</h4>';

	Object.keys(breakdown).forEach(voucher => {
		let voucherData = breakdown[voucher];
		html += `
			<div style="margin-bottom: 30px; border: 1px solid #ddd; padding: 15px;">
				<h5>${voucher} ${voucherData.shipment ? '(Shipment: ' + voucherData.shipment + ')' : ''}</h5>
				<p><strong>Total Applicable Charges:</strong> ${format_currency(voucherData.applicable_charges)}</p>
				
				<table class="table table-sm table-bordered">
					<thead>
						<tr>
							<th>Item</th>
							<th>Amount</th>
							<th>Percentage</th>
							<th>Tax Share</th>
							<th>Total Cost</th>
						</tr>
					</thead>
					<tbody>
		`;

		Object.keys(voucherData.items).forEach(item => {
			let itemData = voucherData.items[item];
			let totalCost = itemData.amount + itemData.total_tax_share;

			html += `
				<tr>
					<td>${item}<br><small>${itemData.item_name}</small></td>
					<td>${format_currency(itemData.amount)}</td>
					<td>${itemData.percentage.toFixed(2)}%</td>
					<td>${format_currency(itemData.total_tax_share)}</td>
					<td>${format_currency(totalCost)}</td>
				</tr>
			`;
		});

		html += '</tbody></table></div>';
	});

	html += '</div>';

	frappe.msgprint({
		title: __("Cost Breakdown"),
		message: html,
		wide: true
	});
}

function validate_report_totals(data) {
	if (!data || data.length === 0) {
		frappe.msgprint(__("No data to validate"));
		return;
	}

	let voucher_validation = {};

	// Group by voucher and calculate totals
	data.forEach(row => {
		let voucher = row.landed_cost_voucher;
		if (!voucher_validation[voucher]) {
			voucher_validation[voucher] = {
				applicable_charges: row.applicable_charges || 0,
				calculated_tax_shares: 0,
				item_percentages: 0,
				items: new Set()
			};
		}

		// Sum tax shares per item (avoid double counting)
		let itemKey = `${voucher}_${row.item_code}`;
		if (!voucher_validation[voucher].items.has(itemKey)) {
			voucher_validation[voucher].calculated_tax_shares += (row.item_tax_share || 0);
			voucher_validation[voucher].item_percentages += (row.item_percentage || 0);
			voucher_validation[voucher].items.add(itemKey);
		}
	});

	let validation_results = [];
	let has_errors = false;

	Object.keys(voucher_validation).forEach(voucher => {
		let validation = voucher_validation[voucher];
		let variance = Math.abs(validation.applicable_charges - validation.calculated_tax_shares);
		let percentage_variance = Math.abs(100 - validation.item_percentages);

		if (variance > 0.01 || percentage_variance > 0.01) {
			has_errors = true;
			validation_results.push(`
				<tr style="color: red;">
					<td>${voucher}</td>
					<td>${format_currency(validation.applicable_charges)}</td>
					<td>${format_currency(validation.calculated_tax_shares)}</td>
					<td>${format_currency(variance)}</td>
					<td>${validation.item_percentages.toFixed(2)}%</td>
				</tr>
			`);
		} else {
			validation_results.push(`
				<tr style="color: green;">
					<td>${voucher}</td>
					<td>${format_currency(validation.applicable_charges)}</td>
					<td>${format_currency(validation.calculated_tax_shares)}</td>
					<td>${format_currency(variance)}</td>
					<td>${validation.item_percentages.toFixed(2)}%</td>
				</tr>
			`);
		}
	});

	let html = `
		<div style="padding: 20px;">
			<h4>Validation Results</h4>
			${has_errors ? '<p style="color: red;">⚠️ Some vouchers have calculation errors!</p>' : '<p style="color: green;">✅ All calculations are correct!</p>'}
			<table class="table table-bordered">
				<thead>
					<tr>
						<th>Voucher</th>
						<th>Expected Total</th>
						<th>Calculated Total</th>
						<th>Variance</th>
						<th>Item Percentages Sum</th>
					</tr>
				</thead>
				<tbody>
					${validation_results.join('')}
				</tbody>
			</table>
		</div>
	`;

	frappe.msgprint({
		title: __("Validation Results"),
		message: html,
		wide: true
	});
}

function export_to_excel(data, columns) {
	// Enhanced export with proper formatting
	if (!data || data.length === 0) {
		frappe.msgprint(__("No data to export"));
		return;
	}

	// Prepare data for export
	let export_data = data.map(row => {
		let export_row = {};
		columns.forEach(col => {
			let value = row[col.fieldname];

			// Format currency fields
			if (["amount", "total_tax_amount", "item_tax_share", "total_landed_cost", "applicable_charges", "rate"].includes(col.fieldname)) {
				export_row[col.label] = value ? parseFloat(value) : 0;
			}
			// Format percentage fields
			else if (["item_percentage"].includes(col.fieldname)) {
				export_row[col.label] = value ? parseFloat(value) : 0;
			}
			else {
				export_row[col.label] = value || '';
			}
		});
		return export_row;
	});

	// Create CSV content
	let csv_content = "data:text/csv;charset=utf-8,";
	let headers = columns.map(col => col.label);
	csv_content += headers.join(",") + "\n";

	export_data.forEach(row => {
		let row_data = headers.map(header => {
			let value = row[header];
			// Escape commas and quotes in text fields
			if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
				value = '"' + value.replace(/"/g, '""') + '"';
			}
			return value;
		});
		csv_content += row_data.join(",") + "\n";
	});

	// Download file
	let encoded_uri = encodeURI(csv_content);
	let link = document.createElement("a");
	link.setAttribute("href", encoded_uri);
	link.setAttribute("download", `landed_cost_allocation_${frappe.datetime.get_today()}.csv`);
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);

	frappe.msgprint(__("Report exported successfully"));
}