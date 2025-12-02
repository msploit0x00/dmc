# RAW VALUES VERSION - No Rounding, No Decimal, No Float Conversion
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
    items_data = get_items_with_raw_calculations(filters, expense_accounts)
    if not items_data:
        return [], []

    # If shipment filter is applied, remove duplicate items by item_code
    if filters.get("shipment_name"):
        items_data = aggregate_items_by_item_code(items_data, expense_accounts)

    # Generate dynamic columns
    columns = generate_horizontal_expense_columns(expense_accounts)

    # Convert to display format - keeping raw values
    final_data = convert_to_horizontal_display_raw_values(
        items_data, expense_accounts)

    return columns, final_data


# def aggregate_items_by_item_code(items_data, expense_accounts):
#     """Aggregate expense accounts for duplicate items when shipment filter is applied"""
#     aggregated = {}

#     for item_data in items_data:
#         item_code = item_data['item_code']

#         if item_code not in aggregated:
#             # First occurrence - keep all data
#             aggregated[item_code] = item_data.copy()
#             # Initialize expense allocations for summing
#             aggregated[item_code]['expense_allocations'] = item_data['expense_allocations'].copy()
#         else:
#             # Subsequent occurrences - only sum the expense_allocations
#             for account_code in expense_accounts.keys():
#                 aggregated[item_code]['expense_allocations'][account_code] += item_data['expense_allocations'].get(
#                     account_code, 0)

#             # Also sum the total_item_tax_share and total_landed_cost
#             aggregated[item_code]['total_item_tax_share'] += item_data['total_item_tax_share']
#             aggregated[item_code]['total_landed_cost'] += item_data['total_landed_cost']

#     return list(aggregated.values())
def aggregate_items_by_item_code(items_data):
    aggregated = {}

    for item in items_data:
        key = (
            item.get("item_code"),
            item.get("item_name"),
            item.get("qty"),
            item.get("uom"),
            item.get("amount"),
            item.get("warehouse"),
        )

        if key not in aggregated:
            aggregated[key] = item
        else:
            # لو تحب تجمع مبلغ الرسوم من الـ landed cost
            aggregated[key]["landed_cost_amount"] += item.get(
                "landed_cost_amount", 0)

    return list(aggregated.values())


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


def get_items_with_raw_calculations(filters, expense_accounts):
    """Get items data with RAW VALUES - no conversion or rounding"""
    conditions = []
    if filters.get("landed_cost_name"):
        conditions.append("lcv.name = %(landed_cost_name)s")
    if filters.get("from_date"):
        conditions.append("lcv.posting_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("lcv.posting_date <= %(to_date)s")

    where_clause = " AND " + " AND ".join(conditions) if conditions else ""

    # Modified query to include item filtering at SQL level
    item_filter_sql = ""
    if filters.get("item"):
        item_filter_sql = """
            AND EXISTS (
                SELECT 1 FROM `tabLanded Cost Item` lci 
                WHERE lci.parent = lcv.name 
                AND lci.item_code = %(item)s
            )
        """

    # Get vouchers that contain the specific item (if filtered)
    try:
        vouchers_sql = f"""
            SELECT 
                lcv.name,
                lcv.total_taxes_and_charges,
                lcv.posting_date
            FROM 
                `tabLanded Cost Voucher` lcv
            WHERE 
                lcv.docstatus = 1
                {where_clause}
                {item_filter_sql}
            ORDER BY lcv.posting_date DESC
        """

        vouchers = frappe.db.sql(vouchers_sql, filters, as_dict=1)
    except Exception as e:
        frappe.log_error(f"Error getting vouchers: {str(e)}")
        return []

    items_data = []
    for voucher in vouchers:
        voucher_name = voucher['name']

        # Get purchase receipts with suppliers
        purchase_receipts_data = get_purchase_receipts_with_supplier(
            voucher_name)
        purchase_receipts_str = ", ".join(
            [pr['receipt'] for pr in purchase_receipts_data])
        suppliers_str = ", ".join(
            list(set([pr['supplier'] for pr in purchase_receipts_data if pr['supplier']])))

        # Get shipment name
        shipment_name = get_shipment_name_safe(voucher_name)

        # Apply shipment filter
        if filters.get("shipment_name") and shipment_name != filters.get("shipment_name"):
            continue

        # Get items for this voucher with item filter applied at SQL level
        try:
            item_conditions = {"parent": voucher_name}
            if filters.get("item"):
                item_conditions["item_code"] = filters.get("item")

            items = frappe.get_all("Landed Cost Item",
                                   filters=item_conditions,
                                   fields=["item_code", "qty", "rate", "amount", "applicable_charges", "custom_usd_amount"])
        except Exception as e:
            frappe.log_error(
                f"Error getting items for {voucher_name}: {str(e)}")
            continue

        if not items:
            continue

        # Process items with RAW VALUES
        voucher_items_data = process_items_with_raw_values(
            items, voucher_name, purchase_receipts_str, suppliers_str, shipment_name, expense_accounts)

        items_data.extend(voucher_items_data)

    return items_data


def get_purchase_receipts_with_supplier(voucher_name):
    """Get purchase receipt numbers with their suppliers from Purchase Receipts table"""
    try:
        receipts = frappe.db.sql("""
            SELECT 
                lcpr.receipt_document,
                lcpr.supplier
            FROM `tabLanded Cost Purchase Receipt` lcpr
            WHERE lcpr.parent = %s AND lcpr.parentfield = 'purchase_receipts'
            ORDER BY lcpr.idx
        """, (voucher_name,), as_dict=1)

        if receipts:
            return [{'receipt': r['receipt_document'], 'supplier': r.get('supplier') or ''} for r in receipts]
        else:
            return [{'receipt': voucher_name, 'supplier': ''}]
    except Exception as e:
        frappe.log_error(
            f"Error getting purchase receipts for {voucher_name}: {str(e)}")
        return [{'receipt': voucher_name, 'supplier': ''}]


def process_items_with_raw_values(items, voucher_name, purchase_receipts_str, suppliers_str, shipment_name, expense_accounts):
    """Process items keeping RAW VALUES - no conversion"""
    voucher_items_data = []

    # Get the tax structure for this voucher - RAW VALUES
    taxes_data = frappe.db.sql("""
        SELECT 
            lct.expense_account,
            lct.amount,
            lct.exchange_rate,
            lct.idx,
            acc.account_currency,
            acc.account_name
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

    # Get company currency
    company = frappe.db.get_value(
        "Landed Cost Voucher", voucher_name, "company")
    company_currency = frappe.db.get_value(
        "Company", company, "default_currency")

    # Convert tax amounts to base currency - KEEP RAW VALUES
    converted_taxes = {}
    total_tax_amount = 0

    for tax in taxes_data:
        expense_account = tax.expense_account
        amount = tax.amount  # RAW VALUE
        exchange_rate = tax.exchange_rate or 1.0  # RAW VALUE
        account_currency = tax.account_currency

        if account_currency and account_currency != company_currency:
            base_amount = amount * exchange_rate  # RAW CALCULATION
        else:
            base_amount = amount  # RAW VALUE

        # SUM amounts if expense account appears multiple times
        if expense_account in converted_taxes:
            # ADD to existing
            converted_taxes[expense_account]['amount'] += base_amount
        else:
            converted_taxes[expense_account] = {
                'amount': base_amount,  # RAW VALUE
                'account_name': tax.account_name or expense_account
            }
        total_tax_amount += base_amount  # RAW ADDITION

    # Use applicable_charges but distribute taxes proportionally - RAW VALUES
    total_applicable_charges = sum(
        [item.get('applicable_charges') or 0 for item in items])  # RAW SUM
    total_item_amount = sum([item.amount for item in items])  # RAW SUM

    # Process each item
    for item in items:
        try:
            item_name = frappe.db.get_value(
                "Item", item.item_code, "item_name") or item.item_code
        except:
            item_name = item.item_code

        item_amount = item.amount  # RAW VALUE
        usd_amount = item.get('custom_usd_amount') or 0  # RAW VALUE
        applicable_charges = item.get('applicable_charges') or 0  # RAW VALUE

        # Calculate item percentage - RAW CALCULATION
        if total_item_amount > 0:
            # RAW CALCULATION
            item_percentage = (item_amount / total_item_amount) * 100
        else:
            item_percentage = 0

        # Distribute taxes based on applicable_charges proportion - RAW CALCULATIONS
        expense_allocations = {}

        if total_applicable_charges > 0:
            item_charges_proportion = applicable_charges / \
                total_applicable_charges  # RAW DIVISION
        else:
            item_charges_proportion = 0

        for expense_account in expense_accounts.keys():
            if expense_account in converted_taxes:
                # Distribute each tax based on item's share - RAW CALCULATION
                tax_amount = converted_taxes[expense_account]['amount']
                item_tax_allocation = tax_amount * item_charges_proportion  # RAW MULTIPLICATION
                # RAW VALUE
                expense_allocations[expense_account] = item_tax_allocation
            else:
                expense_allocations[expense_account] = 0

        # Use the actual applicable_charges as total tax share - RAW VALUE
        total_item_tax_share = applicable_charges  # RAW VALUE
        total_landed_cost = item_amount + applicable_charges  # RAW ADDITION

        # Create item data with RAW VALUES
        item_data = {
            'landed_cost_voucher': voucher_name,
            'purchase_receipt': purchase_receipts_str,
            'supplier': suppliers_str,
            'shipment_name': shipment_name,
            'item_code': item.item_code,
            'item_name': item_name,
            'qty': item.qty,  # RAW VALUE
            'rate': item.rate,  # RAW VALUE
            'amount': item_amount,  # RAW VALUE
            'usd_amount': usd_amount,  # RAW VALUE
            'item_percentage': item_percentage,  # RAW VALUE
            'total_item_tax_share': total_item_tax_share,  # RAW VALUE
            'total_landed_cost': total_landed_cost,  # RAW VALUE
            'expense_allocations': expense_allocations  # RAW VALUES
        }

        voucher_items_data.append(item_data)

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
            "label": _("Supplier"),
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
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
            "label": _("Item Amount USD"),
            "fieldname": "usd_amount",
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


def convert_to_horizontal_display_raw_values(items_data, expense_accounts):
    """Convert items data to horizontal display format - KEEPING RAW VALUES with better separation"""
    display_data = []

    # Group by voucher for better organization
    voucher_groups = {}
    for item_data in items_data:
        voucher = item_data['landed_cost_voucher']
        if voucher not in voucher_groups:
            voucher_groups[voucher] = []
        voucher_groups[voucher].append(item_data)

    # Initialize totals - RAW VALUES
    total_amount = 0
    total_usd_amount = 0
    total_tax_share = 0
    total_landed_cost = 0
    account_totals = {account: 0 for account in expense_accounts.keys()}

    # Process each voucher group
    for voucher_name, voucher_items in voucher_groups.items():
        # Process items in this voucher
        for item_data in voucher_items:
            row = {
                'landed_cost_voucher': item_data['landed_cost_voucher'],
                'purchase_receipt': item_data['purchase_receipt'],
                'supplier': item_data['supplier'],
                'shipment_name': item_data['shipment_name'],
                'item_code': item_data['item_code'],
                'item_name': f"{item_data['item_name']} [{voucher_name}]",
                'qty': item_data['qty'],  # RAW VALUE
                'rate': item_data['rate'],  # RAW VALUE
                'amount': item_data['amount'],  # RAW VALUE
                'usd_amount': item_data['usd_amount'],  # RAW VALUE
                'item_percentage': item_data['item_percentage'],  # RAW VALUE
                'total_item_tax_share': item_data['total_item_tax_share'],
                'total_landed_cost': item_data['total_landed_cost']
            }

            # Add to totals - RAW ADDITION
            total_amount += item_data['amount']
            total_usd_amount += item_data['usd_amount']
            total_tax_share += item_data['total_item_tax_share']
            total_landed_cost += item_data['total_landed_cost']

            # Add expense account allocations - RAW VALUES
            for account_code in expense_accounts.keys():
                safe_fieldname = "expense_" + \
                    str(abs(hash(account_code)) % 100000)
                allocation_amount = item_data['expense_allocations'].get(
                    account_code, 0)

                row[safe_fieldname] = allocation_amount  # RAW VALUE
                account_totals[account_code] += allocation_amount

            display_data.append(row)

    # Add totals row - RAW VALUES
    if display_data:
        totals_row = {
            'landed_cost_voucher': '',
            'purchase_receipt': '',
            'supplier': '',
            'shipment_name': '',
            'item_code': '',
            'item_name': '=== TOTAL ===',
            'qty': '',
            'rate': '',
            'amount': total_amount,  # RAW VALUE
            'usd_amount': total_usd_amount,  # RAW VALUE
            'item_percentage': '',
            'total_item_tax_share': total_tax_share,  # RAW VALUE
            'total_landed_cost': total_landed_cost  # RAW VALUE
        }

        # Add account totals - RAW VALUES
        for account_code in expense_accounts.keys():
            safe_fieldname = "expense_" + str(abs(hash(account_code)) % 100000)
            totals_row[safe_fieldname] = account_totals[account_code]

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
    "name": "Item-Specific Tax Assignment Landed Cost Report - Raw Values",
    "description": "Uses raw values without any rounding or conversion",
    "module": "Stock",
    "report_type": "Script Report",
    "is_standard": "No",
    "disabled": 0
}
