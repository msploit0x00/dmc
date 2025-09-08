// landed_cost_allocation_horizontal.js - Horizontal Layout Version
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
			"options": "Shipment Name",
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

		// Format shipment name as clickable link if it exists
		if (column.fieldname == "shipment_name" && data && data.shipment_name) {
			return `<a href="/app/shipment/${data.shipment_name}" target="_blank" style="color: #0078d4; text-decoration: underline;">${data.shipment_name}</a>`;
		}

		// Format all currency columns (including dynamic account columns)
		if (column.fieldtype === "Currency" ||
			["amount", "total_tax_share", "total_landed_cost", "rate"].includes(column.fieldname) ||
			column.fieldname.startsWith("account_")) {
			if (value && !isNaN(value)) {
				return format_currency(value);
			}
		}

		// Format percentage columns
		if (column.fieldtype === "Percent" || ["item_percentage"].includes(column.fieldname)) {
			if (value && !isNaN(value)) {
				return `${parseFloat(value).toFixed(2)}%`;
			}
		}

		return value;
	},

	"onload": function (report) {
		// Add summary section
		report.page.add_inner_button(__("Show Summary"), function () {
			show_horizontal_summary(report.data, report.columns);
		});

		// Add export button
		report.page.add_inner_button(__("Export to Excel"), function () {
			export_horizontal_to_excel(report.data, report.columns);
		});

		// Add validation button
		report.page.add_inner_button(__("Validate Totals"), function () {
			validate_horizontal_totals(report.data, report.columns);
		});

		// Add account analysis button
		report.page.add_inner_button(__("Account Analysis"), function () {
			show_account_analysis(report.data, report.columns);
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

function show_horizontal_summary(data, columns) {
	if (!data || data.length === 0) {
		frappe.msgprint(__("No data to summarize"));
		return;
	}

	// Get account columns
	let account_columns = columns.filter(col => col.fieldname.startsWith("account_"));

	// Calculate summary statistics
	let summary = calculate_horizontal_summary(data, account_columns);

	let account_summary_html = '';
	if (summary.account_totals.length > 0) {
		account_summary_html = `
			<h5>Account-wise Totals:</h5>
			<table class="table table-bordered table-sm">
				<thead>
					<tr>
						<th>Account</th>
						<th>Total Amount</th>
						<th>Percentage of Total Tax</th>
					</tr>
				</thead>
				<tbody>
		`;

		summary.account_totals.forEach(account => {
			account_summary_html += `
				<tr>
					<td>${account.label}</td>
					<td>${format_currency(account.total)}</td>
					<td>${account.percentage.toFixed(2)}%</td>
				</tr>
			`;
		});

		account_summary_html += '</tbody></table>';
	}

	let html = `
		<div style="padding: 20px;">
			<h4>Landed Cost Summary - Horizontal View</h4>
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
					<td><strong>Total Landed Cost:</strong></td>
					<td>${format_currency(summary.total_landed_cost)}</td>
				</tr>
				<tr>
					<td><strong>Average Item Percentage:</strong></td>
					<td>${summary.avg_item_percentage.toFixed(2)}%</td>
				</tr>
			</table>
			
			${account_summary_html}
		</div>
	`;

	frappe.msgprint({
		title: __("Summary"),
		message: html,
		wide: true
	});
}

function calculate_horizontal_summary(data, account_columns) {
	let vouchers = new Set();
	let shipments = new Set();
	let items = new Set();
	let total_amount = 0;
	let total_taxes = 0;
	let total_landed_cost = 0;
	let total_item_percentage = 0;
	let percentage_count = 0;

	// Account totals
	let account_totals = {};

	data.forEach(row => {
		vouchers.add(row.landed_cost_voucher);
		if (row.shipment_name) shipments.add(row.shipment_name);
		items.add(row.item_code);

		total_amount += (row.amount || 0);
		total_taxes += (row.total_tax_share || 0);
		total_landed_cost += (row.total_landed_cost || 0);

		if (row.item_percentage) {
			total_item_percentage += row.item_percentage;
			percentage_count++;
		}

		// Sum account columns
		account_columns.forEach(col => {
			if (!account_totals[col.fieldname]) {
				account_totals[col.fieldname] = {
					label: col.label,
					total: 0
				};
			}
			account_totals[col.fieldname].total += (row[col.fieldname] || 0);
		});
	});

	// Convert account totals to array with percentages
	let account_totals_array = Object.keys(account_totals).map(key => {
		let account = account_totals[key];
		return {
			label: account.label,
			total: account.total,
			percentage: total_taxes > 0 ? (account.total / total_taxes) * 100 : 0
		};
	}).sort((a, b) => b.total - a.total);

	return {
		total_vouchers: vouchers.size,
		total_shipments: shipments.size,
		total_items: items.size,
		total_amount: total_amount,
		total_taxes: total_taxes,
		total_landed_cost: total_landed_cost,
		avg_item_percentage: percentage_count > 0 ? total_item_percentage / percentage_count : 0,
		account_totals: account_totals_array
	};
}

function show_account_analysis(data, columns) {
	if (!data || data.length === 0) {
		frappe.msgprint(__("No data available for analysis"));
		return;
	}

	// Get account columns
	let account_columns = columns.filter(col => col.fieldname.startsWith("account_"));

	if (account_columns.length === 0) {
		frappe.msgprint(__("No expense account data found"));
		return;
	}

	// Group data by voucher for analysis
	let voucher_analysis = {};

	data.forEach(row => {
		let voucher = row.landed_cost_voucher;
		if (!voucher_analysis[voucher]) {
			voucher_analysis[voucher] = {
				shipment: row.shipment_name,
				items: [],
				account_totals: {}
			};
		}

		// Add item data
		let item_data = {
			item_code: row.item_code,
			item_name: row.item_name,
			amount: row.amount,
			percentage: row.item_percentage,
			accounts: {}
		};

		// Add account data for this item
		account_columns.forEach(col => {
			item_data.accounts[col.label] = row[col.fieldname] || 0;

			// Sum for voucher totals
			if (!voucher_analysis[voucher].account_totals[col.label]) {
				voucher_analysis[voucher].account_totals[col.label] = 0;
			}
			voucher_analysis[voucher].account_totals[col.label] += (row[col.fieldname] || 0);
		});

		voucher_analysis[voucher].items.push(item_data);
	});

	let html = '<div style="padding: 20px;"><h4>Account Analysis by Voucher</h4>';

	Object.keys(voucher_analysis).forEach(voucher => {
		let analysis = voucher_analysis[voucher];

		html += `
			<div style="margin-bottom: 30px; border: 1px solid #ddd; padding: 15px;">
				<h5>${voucher} ${analysis.shipment ? '(Shipment: ' + analysis.shipment + ')' : ''}</h5>
				
				<h6>Account Totals:</h6>
				<div style="display: flex; flex-wrap: wrap; gap: 15px; margin-bottom: 15px;">
		`;

		// Show account totals for this voucher
		Object.keys(analysis.account_totals).forEach(account => {
			html += `
				<div style="background: #f5f5f5; padding: 8px; border-radius: 4px;">
					<strong>${account}:</strong><br>
					${format_currency(analysis.account_totals[account])}
				</div>
			`;
		});

		html += `
				</div>
				
				<h6>Item Breakdown:</h6>
				<table class="table table-sm table-bordered">
					<thead>
						<tr>
							<th>Item</th>
							<th>Amount</th>
							<th>%</th>
		`;

		// Add account headers
		account_columns.forEach(col => {
			html += `<th>${col.label}</th>`;
		});

		html += `
						</tr>
					</thead>
					<tbody>
		`;

		// Add item rows
		analysis.items.forEach(item => {
			html += `
				<tr>
					<td>${item.item_code}<br><small>${item.item_name}</small></td>
					<td>${format_currency(item.amount)}</td>
					<td>${item.percentage.toFixed(2)}%</td>
			`;

			// Add account values for this item
			account_columns.forEach(col => {
				html += `<td>${format_currency(item.accounts[col.label])}</td>`;
			});

			html += '</tr>';
		});

		html += '</tbody></table></div>';
	});

	html += '</div>';

	frappe.msgprint({
		title: __("Account Analysis"),
		message: html,
		wide: true
	});
}

function validate_horizontal_totals(data, columns) {
	if (!data || data.length === 0) {
		frappe.msgprint(__("No data to validate"));
		return;
	}

	// Get account columns
	let account_columns = columns.filter(col => col.fieldname.startsWith("account_"));

	let voucher_validation = {};

	// Group by voucher and validate
	data.forEach(row => {
		let voucher = row.landed_cost_voucher;
		if (!voucher_validation[voucher]) {
			voucher_validation[voucher] = {
				total_tax_share: 0,
				account_sum: 0,
				item_percentages: 0,
				item_count: 0
			};
		}

		voucher_validation[voucher].total_tax_share += (row.total_tax_share || 0);
		voucher_validation[voucher].item_percentages += (row.item_percentage || 0);
		voucher_validation[voucher].item_count++;

		// Sum all account values for this item
		let item_account_sum = 0;
		account_columns.forEach(col => {
			item_account_sum += (row[col.fieldname] || 0);
		});
		voucher_validation[voucher].account_sum += item_account_sum;
	});

	let validation_results = [];
	let has_errors = false;

	Object.keys(voucher_validation).forEach(voucher => {
		let validation = voucher_validation[voucher];

		// Check if total_tax_share equals sum of account columns
		let tax_variance = Math.abs(validation.total_tax_share - validation.account_sum);
		let percentage_variance = Math.abs(100 - validation.item_percentages);

		if (tax_variance > 0.01 || percentage_variance > 0.01) {
			has_errors = true;
			validation_results.push(`
				<tr style="color: red;">
					<td>${voucher}</td>
					<td>${format_currency(validation.total_tax_share)}</td>
					<td>${format_currency(validation.account_sum)}</td>
					<td>${format_currency(tax_variance)}</td>
					<td>${validation.item_percentages.toFixed(2)}%</td>
					<td>${validation.item_count}</td>
				</tr>
			`);
		} else {
			validation_results.push(`
				<tr style="color: green;">
					<td>${voucher}</td>
					<td>${format_currency(validation.total_tax_share)}</td>
					<td>${format_currency(validation.account_sum)}</td>
					<td>${format_currency(tax_variance)}</td>
					<td>${validation.item_percentages.toFixed(2)}%</td>
					<td>${validation.item_count}</td>
				</tr>
			`);
		}
	});

	let html = `
		<div style="padding: 20px;">
			<h4>Validation Results - Horizontal Layout</h4>
			${has_errors ? '<p style="color: red;">⚠️ Some vouchers have calculation errors!</p>' : '<p style="color: green;">✅ All calculations are correct!</p>'}
			<table class="table table-bordered">
				<thead>
					<tr>
						<th>Voucher</th>
						<th>Total Tax Share</th>
						<th>Account Columns Sum</th>
						<th>Variance</th>
						<th>Item Percentages Sum</th>
						<th>Items Count</th>
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

function export_horizontal_to_excel(data, columns) {
	if (!data || data.length === 0) {
		frappe.msgprint(__("No data to export"));
		return;
	}

	// Prepare data for export
	let export_data = data.map(row => {
		let export_row = {};
		columns.forEach(col => {
			let value = row[col.fieldname];

			// Format currency and percentage fields appropriately
			if (col.fieldtype === "Currency" ||
				["amount", "total_tax_share", "total_landed_cost", "rate"].includes(col.fieldname) ||
				col.fieldname.startsWith("account_")) {
				export_row[col.label] = value ? parseFloat(value) : 0;
			}
			else if (col.fieldtype === "Percent" || ["item_percentage"].includes(col.fieldname)) {
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
	link.setAttribute("download", `landed_cost_horizontal_${frappe.datetime.get_today()}.csv`);
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);

	frappe.msgprint(__("Horizontal report exported successfully"));
}