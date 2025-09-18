# FIXED VERSION - NO ROUNDING DIFFERENCES
import frappe
from frappe import _
from frappe.utils import flt
from collections import defaultdict, OrderedDict
from decimal import Decimal, ROUND_HALF_UP


def execute(filters=None):
    """Main execution function for the horizontal expense account report"""
    if not filters:
        filters = {}

    # Get all unique expense accounts first to create columns
    expense_accounts = get_all_expense_accounts(filters)

    if not expense_accounts:
        return [], []

    # Get items data with expense account allocations
    items_data = get_items_with_perfect_match(filters, expense_accounts)

    if not items_data:
        return [], []

    # Generate dynamic columns
    columns = generate_horizontal_expense_columns(expense_accounts)

    # Convert to display format
    final_data = convert_to_horizontal_expense_display(
        items_data, expense_accounts)

    return columns, final_data


def get_all_expense_accounts(filters):
    """Get all unique expense accounts based on filters"""

    # Build conditions
    conditions = []
    if filters.get("landed_cost_name"):
        conditions.append("lcv.name = %(landed_cost_name)s")
    if filters.get("from_date"):
        conditions.append("lcv.posting_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("lcv.posting_date <= %(to_date)s")

    where_clause = " AND " + " AND ".join(conditions) if conditions else ""

    try:
        accounts = frappe.db.sql(f"""
            SELECT DISTINCT
                lct.expense_account,
                acc.account_name
            FROM 
                `tabLanded Cost Voucher` lcv
            INNER JOIN 
                `tabLanded Cost Taxes and Charges` lct ON lcv.name = lct.parent
            LEFT JOIN
                `tabAccount` acc ON lct.expense_account = acc.name
            WHERE 
                lcv.docstatus = 1
                {where_clause}
                AND lct.expense_account IS NOT NULL
                AND lct.expense_account != ''
                AND lct.parentfield = 'taxes'
            ORDER BY acc.account_name, lct.expense_account
        """, filters, as_dict=1)

    except Exception as e:
        frappe.log_error(f"Error getting expense accounts: {str(e)}")
        return OrderedDict()

    expense_accounts = OrderedDict()
    for account in accounts:
        account_code = account['expense_account'].strip()
        if account_code and account_code not in expense_accounts:
            display_name = account.get('account_name') or account_code
            expense_accounts[account_code] = display_name.strip()

    return expense_accounts


def get_items_with_perfect_match(filters, expense_accounts):
    """Get items data with PERFECT MATCH to ERPNext internal calculations"""

    # Build conditions
    conditions = []
    if filters.get("landed_cost_name"):
        conditions.append("name = %(landed_cost_name)s")
    if filters.get("from_date"):
        conditions.append("posting_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("posting_date <= %(to_date)s")

    where_clause = " AND " + " AND ".join(conditions) if conditions else ""

    # Get all vouchers
    try:
        vouchers = frappe.db.sql(f"""
            SELECT 
                name,
                total_taxes_and_charges,
                posting_date
            FROM 
                `tabLanded Cost Voucher`
            WHERE 
                docstatus = 1
                {where_clause}
            ORDER BY posting_date DESC
        """, filters, as_dict=1)
    except Exception as e:
        frappe.log_error(f"Error getting vouchers: {str(e)}")
        return []

    items_data = []

    for voucher in vouchers:
        voucher_name = voucher['name']

        # Get purchase receipts
        purchase_receipts = get_purchase_receipts(voucher_name)
        purchase_receipts_str = ", ".join(purchase_receipts)

        # Get shipment name using safe field checking
        shipment_name = get_shipment_name_safe(voucher_name)

        # Apply shipment filter
        if filters.get("shipment_name") and shipment_name != filters.get("shipment_name"):
            continue

        # Get items for this voucher
        try:
            items = frappe.get_all("Landed Cost Item",
                                   filters={"parent": voucher_name},
                                   fields=["item_code", "qty", "rate", "amount"])
        except Exception as e:
            frappe.log_error(
                f"Error getting items for {voucher_name}: {str(e)}")
            continue

        # Apply item filter
        if filters.get("item"):
            items = [item for item in items if item.item_code ==
                     filters.get("item")]

        if not items:
            continue

        # *** FIXED CALCULATION TO AVOID ROUNDING DIFFERENCES ***
        voucher_items_data = replicate_erpnext_internal_logic_FIXED(
            items, voucher_name, purchase_receipts_str, shipment_name, expense_accounts)

        items_data.extend(voucher_items_data)

    return items_data


def replicate_erpnext_internal_logic_FIXED(items, voucher_name, purchase_receipts_str, shipment_name, expense_accounts):
    """FIXED VERSION: Replicate ERPNext logic but avoid early rounding that causes differences"""

    voucher_items_data = []

    # Get raw data exactly as stored in database
    # Step 1: Get taxes with exact precision as stored
    taxes_data = frappe.db.sql("""
        SELECT 
            lct.expense_account,
            lct.amount,
            lct.exchange_rate,
            lct.idx,
            acc.account_currency
        FROM 
            `tabLanded Cost Taxes and Charges` lct
        LEFT JOIN 
            `tabAccount` acc ON lct.expense_account = acc.name
        WHERE 
            lct.parent = %s
            AND lct.parentfield = 'taxes'
            AND lct.expense_account IS NOT NULL
        ORDER BY lct.idx
    """, (voucher_name,), as_dict=1)

    # Step 2: Get company currency
    company = frappe.db.get_value(
        "Landed Cost Voucher", voucher_name, "company")
    company_currency = frappe.db.get_value(
        "Company", company, "default_currency")

    # Step 3: Calculate converted amounts using Decimal for precision
    converted_taxes = {}
    for tax in taxes_data:
        expense_account = tax.expense_account
        # Use Decimal to avoid floating point precision issues
        amount = Decimal(str(tax.amount))
        exchange_rate = Decimal(str(tax.exchange_rate or 1.0))
        account_currency = tax.account_currency

        # ERPNext conversion logic - EXACT replication using Decimal
        if account_currency and account_currency != company_currency:
            # Convert to base currency
            base_amount = amount * exchange_rate
        else:
            base_amount = amount

        # ERPNext aggregates duplicate accounts at this stage
        if expense_account in converted_taxes:
            converted_taxes[expense_account] += base_amount
        else:
            converted_taxes[expense_account] = base_amount

    # Step 4: Calculate total item amount using Decimal
    total_item_amount = Decimal('0')
    for item in items:
        total_item_amount += Decimal(str(item.amount))

    frappe.log_error(f"=== FIXED CALCULATION DEBUG - {voucher_name} ===")
    frappe.log_error(f"Total Item Amount: {total_item_amount}")

    for account, amount in converted_taxes.items():
        account_name = frappe.db.get_value(
            "Account", account, "account_name") or account
        frappe.log_error(f"Tax {account_name}: {amount}")

    # Step 5: Process each item with precise Decimal calculations
    # IMPORTANT: We'll use distribution logic to ensure totals match exactly

    # First pass: Calculate exact percentages and raw allocations
    item_calculations = []

    for item in items:
        item_amount = Decimal(str(item.amount))

        # Get item name
        try:
            item_name = frappe.db.get_value(
                "Item", item.item_code, "item_name") or item.item_code
        except:
            item_name = item.item_code

        # Calculate percentage with high precision
        if total_item_amount > 0:
            percentage = item_amount / total_item_amount
        else:
            percentage = Decimal('0')

        # Calculate raw allocations (before any rounding)
        raw_expense_allocations = {}
        for expense_account, tax_amount in converted_taxes.items():
            if expense_account in expense_accounts:
                raw_allocation = percentage * tax_amount
                raw_expense_allocations[expense_account] = raw_allocation

        item_calculations.append({
            'item': item,
            'item_name': item_name,
            'item_amount': item_amount,
            'percentage': percentage,
            'raw_expense_allocations': raw_expense_allocations
        })

    # Second pass: Apply intelligent rounding to ensure totals match
    # This is the key fix - we distribute rounding differences

    final_allocations_by_account = {}

    for expense_account in expense_accounts.keys():
        if expense_account not in converted_taxes:
            continue

        expected_total = converted_taxes[expense_account]

        # Calculate rounded allocations
        rounded_allocations = []
        sum_rounded = Decimal('0')

        for calc in item_calculations:
            if expense_account in calc['raw_expense_allocations']:
                raw_value = calc['raw_expense_allocations'][expense_account]
                rounded_value = raw_value.quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                rounded_allocations.append(rounded_value)
                sum_rounded += rounded_value
            else:
                rounded_allocations.append(Decimal('0'))

        # Calculate difference and distribute it
        difference = expected_total - sum_rounded

        frappe.log_error(
            f"Account {expense_account}: Expected={expected_total}, Rounded Sum={sum_rounded}, Diff={difference}")

        # Distribute the difference to the largest allocation(s)
        if abs(difference) > Decimal('0.005'):  # Only adjust if significant difference
            # Find item with largest allocation for this account
            max_index = -1
            max_value = Decimal('0')
            for i, allocation in enumerate(rounded_allocations):
                if allocation > max_value:
                    max_value = allocation
                    max_index = i

            if max_index >= 0:
                rounded_allocations[max_index] += difference
                frappe.log_error(
                    f"  Adjusted item {max_index} by {difference}")

        # Store final allocations
        final_allocations_by_account[expense_account] = rounded_allocations

    # Third pass: Create final item data with corrected allocations
    for i, calc in enumerate(item_calculations):
        item = calc['item']
        item_amount = calc['item_amount']
        percentage = calc['percentage']

        # Build expense allocations from corrected values
        expense_allocations = {}
        total_item_tax_share = Decimal('0')

        for expense_account in expense_accounts.keys():
            if expense_account in final_allocations_by_account:
                allocation = final_allocations_by_account[expense_account][i]
                expense_allocations[expense_account] = float(allocation)
                total_item_tax_share += allocation
            else:
                expense_allocations[expense_account] = 0

        frappe.log_error(
            f"Item {item.item_code}: Tax Share={total_item_tax_share}")

        # Create item data with corrected calculations
        item_data = {
            'landed_cost_voucher': voucher_name,
            'purchase_receipt': purchase_receipts_str,
            'shipment_name': shipment_name,
            'item_code': item.item_code,
            'item_name': calc['item_name'],
            'qty': item.qty,
            'rate': item.rate,
            'amount': float(item_amount),
            'item_percentage': float(percentage * 100),
            'total_item_tax_share': float(total_item_tax_share),
            'total_landed_cost': float(item_amount + total_item_tax_share),
            'expense_allocations': expense_allocations
        }

        voucher_items_data.append(item_data)

    # Final verification - should now show zero differences
    for account_code in expense_accounts.keys():
        if account_code in converted_taxes:
            expected_total = float(converted_taxes[account_code])
            calculated_total = sum([item['expense_allocations'].get(
                account_code, 0) for item in voucher_items_data])
            difference = abs(expected_total - calculated_total)

            account_name = frappe.db.get_value(
                "Account", account_code, "account_name") or account_code
            frappe.log_error(f"FINAL VERIFICATION - {account_name}:")
            frappe.log_error(f"  Expected: {expected_total}")
            frappe.log_error(f"  Calculated: {calculated_total}")
            frappe.log_error(f"  Difference: {difference}")

            if difference > 0.005:  # More than half a cent
                frappe.log_error(f"  *** WARNING: STILL HAS DIFFERENCE ***")
            else:
                frappe.log_error(f"  ✓ PERFECT MATCH ACHIEVED!")

    return voucher_items_data


def get_available_shipment_fields():
    """Dynamically check which shipment-related fields exist in Landed Cost Voucher"""
    try:
        doc_meta = frappe.get_meta("Landed Cost Voucher")
        available_fields = []

        possible_fields = [
            "custom_shipment_name_ref",
            "custom_shipment_name",
            "shipment_name",
            "remarks"
        ]

        existing_fieldnames = [field.fieldname for field in doc_meta.fields]

        for field in possible_fields:
            if field in existing_fieldnames:
                available_fields.append(field)

        return available_fields
    except Exception as e:
        frappe.log_error(f"Error checking shipment fields: {str(e)}")
        return ["remarks"]


def get_shipment_name_safe(voucher_name):
    """Get shipment name using dynamically checked fields"""
    try:
        available_fields = get_available_shipment_fields()

        for field in available_fields:
            try:
                shipment = frappe.db.get_value(
                    "Landed Cost Voucher", voucher_name, field)
                if shipment:
                    return shipment
            except Exception:
                continue

        return ""
    except Exception:
        return ""


def generate_horizontal_expense_columns(expense_accounts):
    """Generate columns with basic item info first, then expense accounts horizontally"""

    columns = [
        {
            "label": _("Landed Cost Voucher"),
            "fieldname": "landed_cost_voucher",
            "fieldtype": "Link",
            "options": "Landed Cost Voucher",
            "width": 150
        },
        {
            "label": _("Purchase Receipt"),
            "fieldname": "purchase_receipt",
            "fieldtype": "Link",
            "options": "Purchase Receipt",
            "width": 120
        },
        {
            "label": _("Shipment Name"),
            "fieldname": "shipment_name",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Qty"),
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 80
        },
        {
            "label": _("Rate"),
            "fieldname": "rate",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": _("Item Amount"),
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Item Percentage"),
            "fieldname": "item_percentage",
            "fieldtype": "Percent",
            "width": 120
        }
    ]

    # Add a column for each expense account
    for account_code, account_display in expense_accounts.items():
        safe_fieldname = "expense_" + str(abs(hash(account_code)) % 100000)

        if ' - ' in account_display:
            parts = account_display.split(' - ')
            clean_display = parts[-1].strip()
        else:
            clean_display = account_display

        if len(clean_display) > 25:
            clean_display = clean_display[:22] + "..."

        clean_display += " (EGP)"

        columns.append({
            "label": _(clean_display),
            "fieldname": safe_fieldname,
            "fieldtype": "Currency",
            "width": 140
        })

    # Add summary columns
    columns.extend([
        {
            "label": _("Total Item Tax Share"),
            "fieldname": "total_item_tax_share",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Total Landed Cost"),
            "fieldname": "total_landed_cost",
            "fieldtype": "Currency",
            "width": 140
        }
    ])

    return columns


def convert_to_horizontal_expense_display(items_data, expense_accounts):
    """Convert items data to horizontal display format with perfect totals"""

    display_data = []

    # Initialize totals using Decimal for precision
    total_amount = Decimal('0')
    total_tax_share = Decimal('0')
    total_landed_cost = Decimal('0')
    account_totals = {account: Decimal('0')
                      for account in expense_accounts.keys()}

    for item_data in items_data:
        row = {
            'landed_cost_voucher': item_data['landed_cost_voucher'],
            'purchase_receipt': item_data['purchase_receipt'],
            'shipment_name': item_data['shipment_name'],
            'item_code': item_data['item_code'],
            'item_name': item_data['item_name'],
            'qty': item_data['qty'],
            'rate': item_data['rate'],
            'amount': item_data['amount'],
            'item_percentage': item_data['item_percentage'],
            'total_item_tax_share': item_data['total_item_tax_share'],
            'total_landed_cost': item_data['total_landed_cost']
        }

        # Add to totals using Decimal precision
        total_amount += Decimal(str(item_data['amount']))
        total_tax_share += Decimal(str(item_data['total_item_tax_share']))
        total_landed_cost += Decimal(str(item_data['total_landed_cost']))

        # Add expense account allocations as horizontal columns
        for account_code in expense_accounts.keys():
            safe_fieldname = "expense_" + str(abs(hash(account_code)) % 100000)
            allocation_amount = item_data['expense_allocations'].get(
                account_code, 0)
            row[safe_fieldname] = allocation_amount
            account_totals[account_code] += Decimal(str(allocation_amount))

        display_data.append(row)

    # Add totals row with perfect precision
    if display_data:
        totals_row = {
            'landed_cost_voucher': '',
            'purchase_receipt': '',
            'shipment_name': '',
            'item_code': '',
            'item_name': 'TOTAL',
            'qty': '',
            'rate': '',
            'amount': float(total_amount),
            'item_percentage': '',
            'total_item_tax_share': float(total_tax_share),
            'total_landed_cost': float(total_landed_cost)
        }

        # Add account totals to totals row
        for account_code in expense_accounts.keys():
            safe_fieldname = "expense_" + str(abs(hash(account_code)) % 100000)
            totals_row[safe_fieldname] = float(account_totals[account_code])

        display_data.append(totals_row)

    return display_data


def get_purchase_receipts(voucher_name):
    """Get purchase receipt numbers from Purchase Receipts table"""
    try:
        receipts = frappe.db.sql("""
            SELECT receipt_document
            FROM `tabLanded Cost Purchase Receipt`
            WHERE parent = %s AND parentfield = 'purchase_receipts'
            ORDER BY idx
        """, (voucher_name,), as_dict=1)

        return [receipt['receipt_document'] for receipt in receipts] if receipts else [voucher_name]
    except Exception as e:
        frappe.log_error(
            f"Error getting purchase receipts for {voucher_name}: {str(e)}")
        return [voucher_name]


# Report configuration
report_config = {
    "name": "FIXED Perfect Match ERPNext Internal Logic Landed Cost Report",
    "description": "Exact replication with NO rounding differences - uses Decimal precision",
    "module": "Stock",
    "report_type": "Script Report",
    "is_standard": "No",
    "disabled": 0
}
