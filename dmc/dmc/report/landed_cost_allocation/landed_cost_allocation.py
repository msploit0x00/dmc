# Enhanced Landed Cost Report - with expense account breakdown and EGP conversion
import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    """Main execution function for the report"""
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    """Define report columns - enhanced with expense account details"""
    return [
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
        },
        {
            "label": _("Expense Account"),
            "fieldname": "expense_account",
            "fieldtype": "Link",
            "options": "Account",
            "width": 150
        },
        {
            "label": _("Account Description"),
            "fieldname": "account_description",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Original Amount"),
            "fieldname": "original_account_amount",
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "label": _("Original Currency"),
            "fieldname": "original_currency",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Exchange Rate"),
            "fieldname": "exchange_rate",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("Total Account Amount (EGP)"),
            "fieldname": "total_account_amount",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Item Share from Account (EGP)"),
            "fieldname": "item_account_share",
            "fieldtype": "Currency",
            "width": 170
        },
        {
            "label": _("Account Share Percentage"),
            "fieldname": "account_share_percentage",
            "fieldtype": "Percent",
            "width": 140
        },
        {
            "label": _("Total Item Tax Share (EGP)"),
            "fieldname": "total_item_tax_share",
            "fieldtype": "Currency",
            "width": 170
        },
        {
            "label": _("Total Landed Cost (EGP)"),
            "fieldname": "total_landed_cost",
            "fieldtype": "Currency",
            "width": 160
        }
    ]


def get_data(filters):
    """Enhanced version - get data with expense account breakdown and EGP conversion"""

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

        # Get purchase receipts for this voucher
        purchase_receipts = get_purchase_receipts(voucher_name)

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

        # Get expense accounts with currency conversion
        expense_accounts = get_expense_accounts_with_conversion(voucher_name)

        if not expense_accounts:
            # If no expense accounts, show items without breakdown
            for item in items:
                purchase_receipts_str = ", ".join(purchase_receipts)
                item_data = process_item_without_accounts(
                    item, voucher, shipment_name, purchase_receipts_str, total_items_amount
                )
                processed_data.append(item_data)
        else:
            # Calculate total converted taxes and charges
            total_converted_taxes = sum(
                [flt(account.get('converted_amount', 0)) for account in expense_accounts])

            # Process each item - ONE ROW PER ITEM PER EXPENSE ACCOUNT
            purchase_receipts_str = ", ".join(purchase_receipts)

            for item in items:
                item_amount = flt(item.amount)
                item_percentage = calculate_percentage(
                    item_amount, total_items_amount)

                # Get item name
                item_name = frappe.db.get_value(
                    "Item", item.item_code, "item_name") or item.item_code

                # Calculate total tax share for this item (using converted amounts)
                total_item_tax_share = (
                    item_percentage / 100) * total_converted_taxes

                # Create a row for each expense account for this item
                for account in expense_accounts:
                    converted_amount = flt(account.get('converted_amount', 0))
                    original_amount = flt(account.get('original_amount', 0))

                    # Item's share from this specific account (using converted amount)
                    item_account_share = (
                        item_percentage / 100) * converted_amount

                    # This item's percentage of this specific account (using converted amount)
                    account_share_percentage = calculate_percentage(
                        item_account_share, converted_amount)

                    processed_data.append({
                        'landed_cost_voucher': voucher_name,
                        'purchase_receipt': purchase_receipts_str,
                        'shipment_name': shipment_name,
                        'item_code': item.item_code,
                        'item_name': item_name,
                        'qty': item.qty,
                        'rate': item.rate,
                        'amount': item_amount,
                        'item_percentage': item_percentage,
                        'expense_account': account['expense_account'],
                        'account_description': account['description'] or '',
                        'original_account_amount': original_amount,
                        'original_currency': account.get('original_currency', 'EGP'),
                        'exchange_rate': account.get('exchange_rate', 1),
                        'total_account_amount': converted_amount,
                        'item_account_share': item_account_share,
                        'account_share_percentage': account_share_percentage,
                        'total_item_tax_share': total_item_tax_share,
                        'total_landed_cost': item_amount + total_item_tax_share
                    })

    return processed_data


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

        # Return list of receipt document names, or voucher name if none found
        if receipts:
            return [receipt['receipt_document'] for receipt in receipts]
        else:
            return [voucher_name]  # Fallback to voucher name

    except Exception as e:
        frappe.log_error(
            f"Error getting purchase receipts for {voucher_name}: {str(e)}")
        return [voucher_name]


def get_expense_accounts_with_conversion(voucher_name):
    """Get expense accounts with currency conversion to EGP"""
    try:
        accounts = frappe.db.sql("""
            SELECT 
                lct.expense_account,
                lct.description,
                lct.amount,
                lct.exchange_rate,
                acc.account_currency
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

            # If account currency is not EGP and exchange rate is provided, convert
            if account_currency and account_currency != 'EGP' and exchange_rate > 0:
                converted_amount = original_amount * exchange_rate
                account['converted_amount'] = converted_amount
                account['conversion_applied'] = True
                account['original_amount'] = original_amount
                account['original_currency'] = account_currency
            else:
                # If currency is EGP or no conversion needed
                account['converted_amount'] = original_amount
                account['conversion_applied'] = False
                account['original_amount'] = original_amount
                account['original_currency'] = account_currency or 'EGP'

        return accounts
    except Exception as e:
        frappe.log_error(
            f"Error getting expense accounts for {voucher_name}: {str(e)}")
        return []


def process_item_without_accounts(item, voucher, shipment_name, purchase_receipt, total_items_amount):
    """Process item when no expense accounts are found"""
    item_amount = flt(item.amount)
    item_percentage = calculate_percentage(item_amount, total_items_amount)

    # Calculate total tax share (assuming EGP since no conversion data available)
    total_tax_share = (item_percentage / 100) * \
        flt(voucher['total_taxes_and_charges'])

    # Get item name
    item_name = frappe.db.get_value(
        "Item", item.item_code, "item_name") or item.item_code

    return {
        'landed_cost_voucher': voucher['name'],
        'purchase_receipt': purchase_receipt,
        'shipment_name': shipment_name,
        'item_code': item.item_code,
        'item_name': item_name,
        'qty': item.qty,
        'rate': item.rate,
        'amount': item_amount,
        'item_percentage': item_percentage,
        'expense_account': '',
        'account_description': 'No expense accounts found',
        'original_account_amount': 0,
        'original_currency': 'EGP',
        'exchange_rate': 1,
        'total_account_amount': 0,
        'item_account_share': 0,
        'account_share_percentage': 0,
        'total_item_tax_share': total_tax_share,
        'total_landed_cost': item_amount + total_tax_share
    }


def get_shipment_name(voucher_name):
    """Get shipment name from voucher"""
    try:
        # Try multiple possible fields for shipment name
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
    "name": "Enhanced Landed Cost Allocation with EGP Conversion",
    "description": "Detailed item-wise allocation of landed costs with expense account breakdown and currency conversion to EGP",
    "module": "Stock",
    "report_type": "Script Report",
    "is_standard": "No",
    "disabled": 0
}
