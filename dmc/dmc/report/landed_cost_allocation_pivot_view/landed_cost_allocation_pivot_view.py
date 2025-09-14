# Horizontal Expense Account Landed Cost Report - Items as Rows, Expense Accounts as Columns
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

    # Get all expense accounts from all relevant vouchers
    accounts = frappe.db.sql(f"""
        SELECT DISTINCT
            lct.expense_account
        FROM 
            `tabLanded Cost Voucher` lcv
        INNER JOIN 
            `tabLanded Cost Taxes and Charges` lct ON lcv.name = lct.parent
        WHERE 
            lcv.docstatus = 1
            {where_clause}
        ORDER BY lct.expense_account
    """, filters, as_dict=1)

    # Return ordered dictionary to maintain order - using expense_account as both key and value
    expense_accounts = OrderedDict()
    for account in accounts:
        expense_accounts[account['expense_account']
                         ] = account['expense_account']

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

    items_data = []

    for voucher in vouchers:
        voucher_name = voucher['name']

        # Get purchase receipts for this voucher
        purchase_receipts = get_purchase_receipts(voucher_name)
        purchase_receipts_str = ", ".join(purchase_receipts)

        # Get shipment name
        shipment_name = get_shipment_name(voucher_name)

        # Apply shipment filter
        if filters.get("shipment_name") and shipment_name != filters.get("shipment_name"):
            continue

        # Get items for this voucher
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
        if total_items_amount == 0:
            continue

        # Get expense accounts for this voucher
        voucher_expense_accounts = get_expense_accounts(voucher_name)

        # Process each item (ONE ROW PER ITEM)
        for item in items:
            item_amount = flt(item.amount)
            item_percentage = calculate_percentage(
                item_amount, total_items_amount)

            # Get item name
            item_name = frappe.db.get_value(
                "Item", item.item_code, "item_name") or item.item_code

            # Calculate total tax share for this item (across all accounts)
            total_item_tax_share = (item_percentage / 100) * \
                flt(voucher['total_taxes_and_charges'])

            # Initialize expense account allocations
            expense_allocations = {
                account: 0 for account in expense_accounts.keys()}

            # Calculate allocations for each expense account
            for account_data in voucher_expense_accounts:
                account_code = account_data['expense_account']
                account_amount = flt(account_data['amount'])

                # Item's share from this specific account
                item_account_share = (item_percentage / 100) * account_amount

                if account_code in expense_allocations:
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

    # Add a column for each expense account (horizontal layout)
    for account_code in expense_accounts.keys():
        # Create safe fieldname from account code
        safe_fieldname = "expense_" + str(abs(hash(account_code)) % 100000)

        # Debug: Print the account_code to understand what we're getting
        frappe.log_error(
            f"Processing account: '{account_code}' (length: {len(account_code)})", "Column Header Debug")

        # Use the actual expense account name as the label
        account_display = account_code.strip()  # Remove any whitespace

        # If account code contains ' - ', take the part after the last ' - '
        if ' - ' in account_display:
            parts = account_display.split(' - ')
            account_display = parts[-1].strip()

        # If still empty or too short, use the full account code
        if not account_display or len(account_display) < 2:
            account_display = account_code.strip()

        # Ensure minimum readable length and truncate if too long
        if len(account_display) > 30:
            account_display = account_display[:27] + "..."
        elif len(account_display) < 3:
            # If still very short, use a more descriptive name
            account_display = f"Acc_{str(abs(hash(account_code)) % 1000)}"

        columns.append({
            "label": _(account_display),
            "fieldname": safe_fieldname,
            "fieldtype": "Currency",
            "width": 140  # Increased width for better display
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

        # Add expense account allocations as horizontal columns
        for unique_key in expense_accounts.keys():
            safe_fieldname = "expense_" + str(abs(hash(unique_key)) % 100000)
            allocation_amount = item_data['expense_allocations'].get(
                unique_key, 0)
            row[safe_fieldname] = allocation_amount

        display_data.append(row)

    return display_data


def get_expense_accounts(voucher_name):
    """Get expense accounts from Landed Cost Taxes table"""
    try:
        accounts = frappe.db.sql("""
            SELECT 
                expense_account,
                description,
                amount
            FROM 
                `tabLanded Cost Taxes and Charges`
            WHERE 
                parent = %s
                AND parentfield = 'taxes'
            ORDER BY idx
        """, (voucher_name,), as_dict=1)

        return accounts
    except Exception as e:
        frappe.log_error(
            f"Error getting expense accounts for {voucher_name}: {str(e)}")
        return []


def get_purchase_receipts(voucher_name):
    """Get purchase receipt numbers from Purchase Receipts table"""
    try:
        receipts = frappe.db.sql("""
            SELECT 
                receipt_document
            FROM 
                `tabLanded Cost Purchase Receipt`
            WHERE 
                parent = %s
                AND parentfield = 'purchase_receipts'
            ORDER BY idx
        """, (voucher_name,), as_dict=1)

        if receipts:
            return [receipt['receipt_document'] for receipt in receipts]
        else:
            return [voucher_name]

    except Exception as e:
        frappe.log_error(
            f"Error getting purchase receipts for {voucher_name}: {str(e)}")
        return [voucher_name]


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
    "name": "Horizontal Expense Account Landed Cost",
    "description": "Items as rows with expense accounts as horizontal columns showing allocations",
    "module": "Stock",
    "report_type": "Script Report",
    "is_standard": "No",
    "disabled": 0
}
