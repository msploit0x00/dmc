# Enhanced Landed Cost Report - Horizontal Layout (No Purchase Receipt Column)
import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    """Main execution function for the report"""
    if not filters:
        filters = {}

    # Get vertical data using original logic
    vertical_data = get_vertical_data(filters)

    if not vertical_data:
        return [], []

    # Get all unique expense accounts for columns
    expense_accounts = get_unique_expense_accounts(vertical_data)

    # Convert vertical data to horizontal layout
    columns = get_columns(expense_accounts)
    horizontal_data = convert_to_horizontal(vertical_data, expense_accounts)

    return columns, horizontal_data


def truncate_text(text, max_length=130):
    """Truncate text to prevent database field length errors"""
    if not text:
        return ""
    text = str(text)
    if len(text) > max_length:
        return text[:max_length-3] + "..."
    return text


def get_vertical_data(filters):
    """Get data using the original vertical logic with fixes"""

    # Build conditions
    conditions = []
    if filters.get("landed_cost_name"):
        conditions.append("name = %(landed_cost_name)s")
    if filters.get("from_date"):
        conditions.append("posting_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("posting_date <= %(to_date)s")

    where_clause = " AND " + " AND ".join(conditions) if conditions else ""

    # Get all submitted vouchers
    vouchers = frappe.db.sql(f"""
        SELECT 
            name,
            total_taxes_and_charges,
            posting_date,
            company
        FROM 
            `tabLanded Cost Voucher`
        WHERE 
            docstatus = 1
            {where_clause}
        ORDER BY posting_date DESC
    """, filters, as_dict=1)

    if not vouchers:
        return []

    processed_data = []

    for voucher in vouchers:
        voucher_name = voucher['name']

        # Get shipment name
        shipment_name = get_shipment_name(voucher_name)

        # Apply shipment filter
        if filters.get("shipment_name") and shipment_name != filters.get("shipment_name"):
            continue

        # Get items
        items = frappe.get_all("Landed Cost Item",
                               filters={"parent": voucher_name},
                               fields=["item_code", "qty", "rate", "amount"])

        # Apply item filter
        if filters.get("item"):
            items = [item for item in items if item.item_code ==
                     filters.get("item")]

        if not items:
            continue

        # Calculate total items amount
        total_items_amount = sum([flt(item.amount) for item in items])

        # Get expense accounts (taxes)
        expense_accounts = get_expense_accounts(voucher_name)

        if not expense_accounts:
            # If no expense accounts, show items without breakdown
            for item in items:
                item_data = process_item_without_accounts(
                    item, voucher, truncate_text(
                        shipment_name), total_items_amount
                )
                processed_data.append(item_data)
        else:
            # Process each item
            for item in items:
                item_amount = flt(item.amount)
                item_percentage = calculate_percentage(
                    item_amount, total_items_amount)

                # Get item name with truncation
                item_name = frappe.db.get_value(
                    "Item", item.item_code, "item_name") or item.item_code
                item_name = truncate_text(item_name)

                # Get shipment name with truncation
                shipment_name_truncated = truncate_text(shipment_name)

                # Calculate total tax share for this item (across all accounts)
                total_item_tax_share = (
                    item_percentage / 100) * flt(voucher['total_taxes_and_charges'])

                # Create a row for each expense account for this item
                for account in expense_accounts:
                    account_amount = flt(account['amount'])

                    # Item's share from this specific account
                    item_account_share = (
                        item_percentage / 100) * account_amount

                    # This item's percentage of this specific account
                    account_share_percentage = calculate_percentage(
                        item_account_share, account_amount)

                    processed_data.append({
                        'landed_cost_voucher': voucher_name,
                        'shipment_name': shipment_name_truncated,
                        'item_code': item.item_code,
                        'item_name': item_name,
                        'qty': item.qty,
                        'rate': item.rate,
                        'amount': item_amount,
                        'item_percentage': item_percentage,
                        'expense_account': truncate_text(account['expense_account']),
                        'total_account_amount': account_amount,
                        'item_account_share': item_account_share,
                        'account_share_percentage': account_share_percentage,
                        'total_item_tax_share': total_item_tax_share,
                        'total_landed_cost': item_amount + total_item_tax_share
                    })

    return processed_data


def get_unique_expense_accounts(vertical_data):
    """Extract unique expense accounts from vertical data"""
    accounts = {}
    for row in vertical_data:
        if row.get('expense_account'):
            accounts[row['expense_account']] = {
                'expense_account': row['expense_account'],
            }

    return list(accounts.values())


def convert_to_horizontal(vertical_data, expense_accounts):
    """Convert vertical data to horizontal layout - one row per item"""
    if not vertical_data:
        return []

    # Group data by unique item combination (voucher + item_code)
    grouped_data = {}

    for row in vertical_data:
        key = f"{row['landed_cost_voucher']}_{row['item_code']}"

        if key not in grouped_data:
            # Initialize base item data with truncation
            grouped_data[key] = {
                'landed_cost_voucher': row['landed_cost_voucher'],
                'shipment_name': truncate_text(row['shipment_name']),
                'item_code': row['item_code'],
                'item_name': truncate_text(row['item_name']),
                'qty': row['qty'],
                'rate': row['rate'],
                'amount': row['amount'],
                'item_percentage': row['item_percentage'],
                'total_item_tax_share': row['total_item_tax_share'],
                'total_landed_cost': row['total_landed_cost'],
                'accounts': {}
            }

        # Add account data - sum amounts if same account appears multiple times
        if row.get('expense_account'):
            account = row['expense_account']
            if account in grouped_data[key]['accounts']:
                grouped_data[key]['accounts'][account] += row['item_account_share']
            else:
                grouped_data[key]['accounts'][account] = row['item_account_share']

    # Convert to horizontal format
    horizontal_data = []

    for item_data in grouped_data.values():
        row = {
            'landed_cost_voucher': item_data['landed_cost_voucher'],
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

        # Add account columns
        for account in expense_accounts:
            account_key = get_account_fieldname(account['expense_account'])
            row[account_key] = item_data['accounts'].get(
                account['expense_account'], 0)

        horizontal_data.append(row)

    return horizontal_data


def get_columns(expense_accounts):
    """Define report columns - fixed columns plus dynamic expense account columns"""

    # Fixed columns
    columns = [
        {
            "label": _("Landed Cost Voucher"),
            "fieldname": "landed_cost_voucher",
            "fieldtype": "Link",
            "options": "Landed Cost Voucher",
            "width": 150
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

    # Add dynamic columns for each expense account
    for account in expense_accounts:
        account_key = get_account_fieldname(account['expense_account'])
        # Truncate account name for label if too long
        account_label = truncate_text(account['expense_account'], 25)
        columns.append({
            "label": _(account_label),
            "fieldname": account_key,
            "fieldtype": "Currency",
            "width": 130
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


def get_account_fieldname(account_name):
    """Convert account name to valid fieldname"""
    import re
    fieldname = re.sub(r'[^a-zA-Z0-9]', '_', account_name.lower())
    fieldname = re.sub(r'_+', '_', fieldname)
    fieldname = fieldname.strip('_')
    return f"account_{fieldname}"


def get_expense_accounts(voucher_name):
    """Get expense accounts from Landed Cost Taxes table"""
    try:
        all_accounts = frappe.db.sql("""
            SELECT 
                expense_account,
                amount,
                idx
            FROM 
                `tabLanded Cost Taxes and Charges`
            WHERE 
                parent = %s
                AND parentfield = 'taxes'
                AND expense_account IS NOT NULL
                AND expense_account != ''
            ORDER BY idx
        """, (voucher_name,), as_dict=1)

        # Remove duplicates but keep legitimate separate entries
        cleaned_accounts = []
        seen_combinations = set()

        for account in all_accounts:
            key = f"{account['expense_account']}_{account['amount']}_{account['idx']}"

            if key not in seen_combinations:
                cleaned_accounts.append({
                    'expense_account': account['expense_account'],
                    'amount': flt(account['amount'])
                })
                seen_combinations.add(key)

        return cleaned_accounts

    except Exception:
        return []


def process_item_without_accounts(item, voucher, shipment_name, total_items_amount):
    """Process item when no expense accounts are found"""
    item_amount = flt(item.amount)
    item_percentage = calculate_percentage(item_amount, total_items_amount)

    # Calculate total tax share
    total_tax_share = (item_percentage / 100) * \
        flt(voucher['total_taxes_and_charges'])

    # Get item name with truncation
    item_name = frappe.db.get_value(
        "Item", item.item_code, "item_name") or item.item_code
    item_name = truncate_text(item_name)

    return {
        'landed_cost_voucher': voucher['name'],
        'shipment_name': truncate_text(shipment_name),
        'item_code': item.item_code,
        'item_name': item_name,
        'qty': item.qty,
        'rate': item.rate,
        'amount': item_amount,
        'item_percentage': item_percentage,
        'expense_account': '',
        'total_account_amount': 0,
        'item_account_share': 0,
        'account_share_percentage': 0,
        'total_item_tax_share': total_tax_share,
        'total_landed_cost': item_amount + total_tax_share
    }


def get_shipment_name(voucher_name):
    """Get shipment name from voucher"""
    try:
        fields_to_try = [
            "custom_shipment_name_ref",
            "custom_shipment_name",
            "shipment_name",
            "remarks"
        ]

        for field in fields_to_try:
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


def calculate_percentage(part, total):
    """Calculate percentage with safe division"""
    if not total or total == 0:
        return 0
    return flt((part / total) * 100, 2)


# Report configuration for Frappe
report_config = {
    "name": "Enhanced Landed Cost Allocation - Clean",
    "description": "Item-wise allocation of landed costs with expense accounts as horizontal columns (Clean Version)",
    "module": "Stock",
    "report_type": "Script Report",
    "is_standard": "No",
    "disabled": 0
}
