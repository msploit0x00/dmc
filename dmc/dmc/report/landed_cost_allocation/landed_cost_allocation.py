# Enhanced Landed Cost Report - with expense account breakdown
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
            "label": _("Total Account Amount"),
            "fieldname": "total_account_amount",
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "label": _("Item Share from Account"),
            "fieldname": "item_account_share",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Account Share Percentage"),
            "fieldname": "account_share_percentage",
            "fieldtype": "Percent",
            "width": 140
        },
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
    ]


def get_data(filters):
    """Enhanced version - get data with expense account breakdown"""

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

        # Get expense accounts (taxes)
        expense_accounts = get_expense_accounts(voucher_name)

        if not expense_accounts:
            # If no expense accounts, show items without breakdown
            for item in items:
                purchase_receipts_str = ", ".join(purchase_receipts)
                item_data = process_item_without_accounts(
                    item, voucher, shipment_name, purchase_receipts_str, total_items_amount
                )
                processed_data.append(item_data)
        else:
            # Process each item - ONE ROW PER ITEM PER EXPENSE ACCOUNT
            purchase_receipts_str = ", ".join(purchase_receipts)

            for item in items:
                item_amount = flt(item.amount)
                item_percentage = calculate_percentage(
                    item_amount, total_items_amount)

                # Get item name
                item_name = frappe.db.get_value(
                    "Item", item.item_code, "item_name") or item.item_code

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
                        'total_account_amount': account_amount,
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


def process_item_without_accounts(item, voucher, shipment_name, purchase_receipt, total_items_amount):
    """Process item when no expense accounts are found"""
    item_amount = flt(item.amount)
    item_percentage = calculate_percentage(item_amount, total_items_amount)

    # Calculate total tax share
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
    "name": "Enhanced Landed Cost Allocation",
    "description": "Detailed item-wise allocation of landed costs with expense account breakdown",
    "module": "Stock",
    "report_type": "Script Report",
    "is_standard": "No",
    "disabled": 0
}
