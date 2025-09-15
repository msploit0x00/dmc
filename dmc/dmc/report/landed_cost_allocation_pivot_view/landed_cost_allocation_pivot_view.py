# Safe Horizontal Expense Account Landed Cost Report - Checks Field Existence
import frappe
from frappe import _
from frappe.utils import flt
from collections import defaultdict, OrderedDict


def execute(filters=None):
    """Main execution function for the horizontal expense account report"""
    if not filters:
        filters = {}

    # Get all unique expense accounts first to create columns
    expense_accounts = get_all_expense_accounts(filters)

    if not expense_accounts:
        return [], []

    # Get items data with expense account allocations
    items_data = get_items_with_expense_allocations(filters, expense_accounts)

    if not items_data:
        return [], []

    # Generate dynamic columns
    columns = generate_horizontal_expense_columns(expense_accounts)

    # Convert to display format
    final_data = convert_to_horizontal_expense_display(
        items_data, expense_accounts)

    return columns, final_data


def get_available_shipment_fields():
    """Dynamically check which shipment-related fields exist in Landed Cost Voucher"""
    try:
        # Get the doctype structure
        doc_meta = frappe.get_meta("Landed Cost Voucher")
        available_fields = []

        # Check common shipment field names
        possible_fields = [
            "custom_shipment_name_ref",
            "custom_shipment_name",
            "shipment_name",
            "remarks"
        ]

        # Get actual fieldnames from meta
        existing_fieldnames = [field.fieldname for field in doc_meta.fields]

        for field in possible_fields:
            if field in existing_fieldnames:
                available_fields.append(field)

        return available_fields
    except Exception as e:
        frappe.log_error(f"Error checking shipment fields: {str(e)}")
        return ["remarks"]  # Fallback to remarks which should always exist


def get_all_expense_accounts(filters):
    """Get all unique expense accounts based on filters - with safe field checking"""

    # Build conditions
    conditions = []
    if filters.get("landed_cost_name"):
        conditions.append("lcv.name = %(landed_cost_name)s")
    if filters.get("from_date"):
        conditions.append("lcv.posting_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("lcv.posting_date <= %(to_date)s")

    where_clause = " AND " + " AND ".join(conditions) if conditions else ""

    # Get all expense accounts from relevant vouchers
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
            ORDER BY lct.expense_account
        """, filters, as_dict=1)
    except Exception as e:
        frappe.log_error(f"Error getting expense accounts: {str(e)}")
        return OrderedDict()

    # Return ordered dictionary maintaining account order
    expense_accounts = OrderedDict()
    for account in accounts:
        account_code = account['expense_account'].strip()
        if account_code and account_code not in expense_accounts:
            # Use account name if available, otherwise use account code
            display_name = account.get('account_name') or account_code
            expense_accounts[account_code] = display_name.strip()

    return expense_accounts


def get_items_with_expense_allocations(filters, expense_accounts):
    """Get items data with expense account allocations"""

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

        # Calculate total items amount
        total_items_amount = sum([flt(item.amount) for item in items])
        if total_items_amount == 0:
            continue

        # Get expense accounts for this voucher with conversion
        voucher_expense_accounts = get_expense_accounts_with_conversion(
            voucher_name)

        # Filter expense accounts to only include those in our master list
        filtered_expense_accounts = []
        for account_data in voucher_expense_accounts:
            if account_data['expense_account'] in expense_accounts:
                filtered_expense_accounts.append(account_data)

        # Calculate total converted taxes for this voucher
        total_converted_taxes = sum([flt(account.get('converted_amount', 0))
                                     for account in filtered_expense_accounts])

        # Process each item
        for item in items:
            item_amount = flt(item.amount)
            item_percentage = calculate_percentage(
                item_amount, total_items_amount)

            # Get item name
            try:
                item_name = frappe.db.get_value(
                    "Item", item.item_code, "item_name") or item.item_code
            except:
                item_name = item.item_code

            # Calculate total tax share for this item
            total_item_tax_share = (
                item_percentage / 100) * total_converted_taxes

            # Initialize expense account allocations for ALL accounts (including zeros)
            expense_allocations = {
                account: 0 for account in expense_accounts.keys()}

            # Calculate allocations for each expense account that exists for this voucher
            for account_data in filtered_expense_accounts:
                account_code = account_data['expense_account']
                converted_amount = flt(account_data.get('converted_amount', 0))

                # Item's share from this specific account
                item_account_share = (item_percentage / 100) * converted_amount
                expense_allocations[account_code] = item_account_share

            # Create item data
            item_data = {
                'landed_cost_voucher': voucher_name,
                'purchase_receipt': purchase_receipts_str,
                'shipment_name': shipment_name,
                'item_code': item.item_code,
                'item_name': item_name,
                'qty': item.qty,
                'rate': item.rate,
                'amount': item_amount,
                'item_percentage': item_percentage,
                'total_item_tax_share': total_item_tax_share,
                'total_landed_cost': item_amount + total_item_tax_share,
                'expense_allocations': expense_allocations
            }

            items_data.append(item_data)

    return items_data


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


def get_expense_accounts_with_conversion(voucher_name):
    """Get expense accounts with currency conversion to EGP"""
    try:
        accounts = frappe.db.sql("""
            SELECT 
                lct.expense_account,
                lct.description,
                lct.amount,
                lct.exchange_rate,
                acc.account_currency,
                acc.account_name
            FROM 
                `tabLanded Cost Taxes and Charges` lct
            LEFT JOIN 
                `tabAccount` acc ON lct.expense_account = acc.name
            WHERE 
                lct.parent = %s
                AND lct.parentfield = 'taxes'
            ORDER BY lct.idx
        """, (voucher_name,), as_dict=1)

        # Convert amounts to EGP
        for account in accounts:
            original_amount = flt(account.get('amount', 0))
            account_currency = account.get('account_currency', '').upper()
            exchange_rate = flt(account.get('exchange_rate', 1))

            # Currency conversion logic
            if account_currency and account_currency != 'EGP' and exchange_rate > 0:
                converted_amount = original_amount * exchange_rate
                account['converted_amount'] = converted_amount
                account['original_amount'] = original_amount
                account['original_currency'] = account_currency
                account['exchange_rate'] = exchange_rate
            else:
                account['converted_amount'] = original_amount
                account['original_amount'] = original_amount
                account['original_currency'] = account_currency or 'EGP'
                account['exchange_rate'] = 1

        return accounts
    except Exception as e:
        frappe.log_error(
            f"Error getting expense accounts for {voucher_name}: {str(e)}")
        return []


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
        # Create safe fieldname
        safe_fieldname = "expense_" + str(abs(hash(account_code)) % 100000)

        # Clean display name
        if ' - ' in account_display:
            parts = account_display.split(' - ')
            clean_display = parts[-1].strip()
        else:
            clean_display = account_display

        # Truncate if too long
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
    """Convert items data to horizontal display format"""

    display_data = []

    # Initialize totals for summary row
    total_amount = 0
    total_tax_share = 0
    total_landed_cost = 0
    account_totals = {account: 0 for account in expense_accounts.keys()}

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

        # Add to totals
        total_amount += flt(item_data['amount'])
        total_tax_share += flt(item_data['total_item_tax_share'])
        total_landed_cost += flt(item_data['total_landed_cost'])

        # Add expense account allocations as horizontal columns
        for account_code in expense_accounts.keys():
            safe_fieldname = "expense_" + str(abs(hash(account_code)) % 100000)
            allocation_amount = item_data['expense_allocations'].get(
                account_code, 0)
            row[safe_fieldname] = allocation_amount
            account_totals[account_code] += allocation_amount

        display_data.append(row)

    # Add totals row
    if display_data:
        totals_row = {
            'landed_cost_voucher': '',
            'purchase_receipt': '',
            'shipment_name': '',
            'item_code': '',
            'item_name': 'TOTAL',
            'qty': '',
            'rate': '',
            'amount': total_amount,
            'item_percentage': '',
            'total_item_tax_share': total_tax_share,
            'total_landed_cost': total_landed_cost
        }

        # Add account totals to totals row
        for account_code in expense_accounts.keys():
            safe_fieldname = "expense_" + str(abs(hash(account_code)) % 100000)
            totals_row[safe_fieldname] = account_totals[account_code]

        display_data.append(totals_row)

    return display_data


# Utility functions
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


def calculate_percentage(part, total):
    """Calculate percentage with safe division"""
    if not total or total == 0:
        return 0
    return flt((part / total) * 100, 2)


# Report configuration
report_config = {
    "name": "Safe Horizontal Expense Account Landed Cost",
    "description": "Items as rows with expense accounts as horizontal columns (Safe field checking)",
    "module": "Stock",
    "report_type": "Script Report",
    "is_standard": "No",
    "disabled": 0
}
