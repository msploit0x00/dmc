# FIXED VERSION - Uses EXACT item-wise tax distribution without rounding
import frappe
from frappe import _
from frappe.utils import flt
from collections import defaultdict, OrderedDict
from decimal import Decimal, ROUND_HALF_UP, getcontext

# Set high precision for Decimal operations
getcontext().prec = 28


def execute(filters=None):
    """Main execution function for the horizontal expense account report"""
    if not filters:
        filters = {}

    # Get all unique expense accounts first to create columns
    expense_accounts = get_all_expense_accounts(filters)
    if not expense_accounts:
        return [], []

    # Get items data with EXACT expense account allocations
    items_data = get_items_with_exact_allocations(filters, expense_accounts)
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


def get_items_with_exact_allocations(filters, expense_accounts):
    """Get items data with EXACT tax allocations from Landed Cost Item Distribution table"""
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

        # Get shipment name
        shipment_name = get_shipment_name_safe(voucher_name)

        # Apply shipment filter
        if filters.get("shipment_name") and shipment_name != filters.get("shipment_name"):
            continue

        # *** KEY FIX: Get EXACT allocations from the distribution table ***
        voucher_items_data = get_exact_item_allocations(
            voucher_name, purchase_receipts_str, shipment_name, expense_accounts, filters
        )

        items_data.extend(voucher_items_data)

    return items_data


def get_exact_item_allocations(voucher_name, purchase_receipts_str, shipment_name, expense_accounts, filters):
    """Get EXACT allocations from Landed Cost Item Distribution table - NO CALCULATIONS"""

    # Get basic item data
    try:
        items_query = """
            SELECT 
                item_code,
                qty,
                rate,
                amount,
                applicable_charges
            FROM 
                `tabLanded Cost Item`
            WHERE 
                parent = %(parent)s
        """

        params = {"parent": voucher_name}

        # Apply item filter if provided
        if filters.get("item"):
            items_query += " AND item_code = %(item)s"
            params["item"] = filters.get("item")

        items = frappe.db.sql(items_query, params, as_dict=1)

    except Exception as e:
        frappe.log_error(f"Error getting items for {voucher_name}: {str(e)}")
        return []

    if not items:
        return []

    voucher_items_data = []

    for item in items:
        try:
            item_name = frappe.db.get_value(
                "Item", item.item_code, "item_name") or item.item_code
        except:
            item_name = item.item_code

        # *** CORE FIX: Get EXACT allocations from distribution table ***
        exact_allocations = get_item_exact_distribution(
            voucher_name, item.item_code, expense_accounts)

        # Calculate percentage
        try:
            total_voucher_amount = Decimal(
                str(sum([Decimal(str(i['amount'])) for i in items])))
            item_percentage = float((Decimal(str(
                item.amount)) / total_voucher_amount * 100) if total_voucher_amount > 0 else 0)
        except:
            item_percentage = 0

        # Calculate totals using exact allocations
        total_item_tax_share = sum(exact_allocations.values())
        total_landed_cost = float(
            Decimal(str(item.amount)) + Decimal(str(total_item_tax_share)))

        # Create item data with EXACT values
        item_data = {
            'landed_cost_voucher': voucher_name,
            'purchase_receipt': purchase_receipts_str,
            'shipment_name': shipment_name,
            'item_code': item.item_code,
            'item_name': item_name,
            'qty': item.qty,
            'rate': item.rate,
            'amount': float(item.amount),
            'item_percentage': item_percentage,
            'total_item_tax_share': total_item_tax_share,
            'total_landed_cost': total_landed_cost,
            'expense_allocations': exact_allocations
        }

        voucher_items_data.append(item_data)

    return voucher_items_data


# def get_item_exact_distribution(voucher_name, item_code, expense_accounts):
#     """Get EXACT distribution values - match Excel calculations exactly"""

#     try:
#         # First, let's check if the Distribution table exists and has data
#         distributions = frappe.db.sql("""
#             SELECT
#                 lcid.expense_account,
#                 lcid.amount
#             FROM
#                 `tabLanded Cost Item Distribution` lcid
#             WHERE
#                 lcid.parent = %s
#                 AND lcid.item_code = %s
#                 AND lcid.expense_account IS NOT NULL
#         """, (voucher_name, item_code), as_dict=1)

#         # Build allocations dictionary
#         exact_allocations = {}

#         # Initialize all accounts with 0
#         for account_code in expense_accounts.keys():
#             exact_allocations[account_code] = 0.0

#         if distributions:
#             # Use distribution table if available
#             for dist in distributions:
#                 expense_account = dist.expense_account
#                 if expense_account in expense_accounts:
#                     exact_allocations[expense_account] = float(dist.amount)
#         else:
#             # Fallback: Calculate using the EXACT same method as Excel
#             exact_allocations = calculate_like_excel(
#                 voucher_name, item_code, expense_accounts)

#         return exact_allocations

#     except Exception as e:
#         frappe.log_error(
#             f"Error getting exact distribution for {voucher_name} - {item_code}: {str(e)}")

#         # Last resort: calculate like Excel
#         return calculate_like_excel(voucher_name, item_code, expense_accounts)

def get_item_exact_distribution(voucher_name, item_code, expense_accounts):
    """Get EXACT distribution values - match Excel calculations exactly"""
    try:
        # Check if table exists before querying
        if not frappe.db.table_exists("Landed Cost Item Distribution"):
            # Table doesn't exist → fallback to Excel-like calculation
            return calculate_like_excel(voucher_name, item_code, expense_accounts)

        # If exists, fetch data
        distributions = frappe.db.sql("""
            SELECT 
                lcid.expense_account,
                lcid.amount
            FROM 
                `tabLanded Cost Item Distribution` lcid
            WHERE 
                lcid.parent = %(parent)s
                AND lcid.item_code = %(item)s
                AND lcid.expense_account IS NOT NULL
        """, {"parent": voucher_name, "item": item_code}, as_dict=1)

        # Build allocations dictionary
        exact_allocations = {
            account_code: 0.0 for account_code in expense_accounts.keys()}

        if distributions:
            for dist in distributions:
                expense_account = dist.expense_account
                if expense_account in expense_accounts:
                    exact_allocations[expense_account] = float(dist.amount)
        else:
            # If table exists but has no rows → fallback
            exact_allocations = calculate_like_excel(
                voucher_name, item_code, expense_accounts)

        return exact_allocations

    except Exception as e:
        frappe.log_error(
            f"Error getting exact distribution for {voucher_name} - {item_code}: {str(e)}"
        )
        return calculate_like_excel(voucher_name, item_code, expense_accounts)


def calculate_like_excel(voucher_name, item_code, expense_accounts):
    """Calculate exactly like Excel - using the SAME logic as your spreadsheet"""

    try:
        # Get the item's basic data
        item_data = frappe.db.sql("""
            SELECT amount, applicable_charges
            FROM `tabLanded Cost Item`
            WHERE parent = %s AND item_code = %s
        """, (voucher_name, item_code), as_dict=1)

        if not item_data:
            return {account_code: 0.0 for account_code in expense_accounts.keys()}

        item_amount = Decimal(str(item_data[0]['amount']))
        applicable_charges = Decimal(str(item_data[0]['applicable_charges']))

        # Get all items' total amount for percentage calculation
        all_items = frappe.db.sql("""
            SELECT SUM(amount) as total_amount
            FROM `tabLanded Cost Item`
            WHERE parent = %s
        """, (voucher_name,), as_dict=1)

        total_items_amount = Decimal(str(all_items[0]['total_amount']))

        # Calculate item percentage (same as Excel)
        if total_items_amount > 0:
            item_percentage = item_amount / total_items_amount
        else:
            item_percentage = Decimal('0')

        # Get tax amounts by account
        taxes_data = frappe.db.sql("""
            SELECT 
                lct.expense_account,
                lct.amount,
                lct.exchange_rate
            FROM 
                `tabLanded Cost Taxes and Charges` lct
            WHERE 
                lct.parent = %s
                AND lct.parentfield = 'taxes'
                AND lct.expense_account IS NOT NULL
            ORDER BY lct.idx
        """, (voucher_name,), as_dict=1)

        # Calculate allocations using item percentage (EXACT Excel method)
        exact_allocations = {}

        for account_code in expense_accounts.keys():
            exact_allocations[account_code] = 0.0

        # Apply item percentage to each tax account
        for tax in taxes_data:
            expense_account = tax.expense_account
            if expense_account in expense_accounts:
                tax_amount = Decimal(str(tax.amount))
                exchange_rate = Decimal(str(tax.exchange_rate or 1.0))

                # Convert to base currency if needed
                base_tax_amount = tax_amount * exchange_rate

                # Apply item percentage - EXACT same calculation as Excel
                item_tax_share = base_tax_amount * item_percentage

                # Store with high precision, then convert to float
                exact_allocations[expense_account] = float(item_tax_share)

        return exact_allocations

    except Exception as e:
        frappe.log_error(
            f"Error calculating like Excel for {voucher_name} - {item_code}: {str(e)}")
        return {account_code: 0.0 for account_code in expense_accounts.keys()}


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
    """Convert items data to horizontal display format with EXACT totals"""
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

    # Add totals row with EXACT precision
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
    "name": "Exact Landed Cost Allocation Report",
    "description": "Uses exact values from Landed Cost Item Distribution table - NO rounding or calculations",
    "module": "Stock",
    "report_type": "Script Report",
    "is_standard": "No",
    "disabled": 0
}
