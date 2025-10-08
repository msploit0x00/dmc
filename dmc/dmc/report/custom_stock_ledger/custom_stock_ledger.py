# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import copy
from collections import defaultdict

import frappe
from frappe import _
from frappe.query_builder.functions import CombineDatetime, Sum
from frappe.utils import cint, flt, get_datetime

from erpnext.stock.doctype.inventory_dimension.inventory_dimension import get_inventory_dimensions
from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos
from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import get_stock_balance_for
from erpnext.stock.doctype.warehouse.warehouse import apply_warehouse_filter
from erpnext.stock.utils import (
    is_reposting_item_valuation_in_progress,
    update_included_uom_in_report,
)


def execute(filters=None):
    # أول حاجة: لو عايز pivot view
    if filters and filters.get("show_pivot_view"):
        return get_pivot_data(filters)

    # الكود العادي يكمل
    is_reposting_item_valuation_in_progress()
    include_uom = filters.get("include_uom")
    columns = get_columns(filters)
    items = get_items(filters)
    sl_entries = get_stock_ledger_entries(filters, items)
    item_details = get_item_details(items, sl_entries, include_uom)
    if filters.get("batch_no"):
        opening_row = get_opening_balance_from_batch(
            filters, columns, sl_entries)
    else:
        opening_row = get_opening_balance(filters, columns, sl_entries)

    precision = cint(frappe.db.get_single_value(
        "System Settings", "float_precision"))
    bundle_details = {}

    if filters.get("segregate_serial_batch_bundle"):
        bundle_details = get_serial_batch_bundle_details(sl_entries, filters)

    data = []
    conversion_factors = []
    if opening_row:
        data.append(opening_row)
        conversion_factors.append(0)

    actual_qty = stock_value = 0
    if opening_row:
        actual_qty = opening_row.get("qty_after_transaction")
        stock_value = opening_row.get("stock_value")

    available_serial_nos = {}
    inventory_dimension_filters_applied = check_inventory_dimension_filters_applied(
        filters)

    batch_balance_dict = frappe._dict({})
    if actual_qty and filters.get("batch_no"):
        batch_balance_dict[filters.batch_no] = [actual_qty, stock_value]

    for sle in sl_entries:
        item_detail = item_details[sle.item_code]

        sle.update(item_detail)
        if bundle_info := bundle_details.get(sle.serial_and_batch_bundle):
            data.extend(get_segregated_bundle_entries(
                sle, bundle_info, batch_balance_dict, filters))
            continue

        if filters.get("batch_no") or inventory_dimension_filters_applied:
            actual_qty += flt(sle.actual_qty, precision)
            stock_value += sle.stock_value_difference
            if sle.batch_no:
                if not batch_balance_dict.get(sle.batch_no):
                    batch_balance_dict[sle.batch_no] = [0, 0]

                batch_balance_dict[sle.batch_no][0] += sle.actual_qty

            if filters.get("segregate_serial_batch_bundle"):
                actual_qty = batch_balance_dict[sle.batch_no][0]

            if sle.voucher_type == "Stock Reconciliation" and not sle.actual_qty:
                actual_qty = sle.qty_after_transaction
                stock_value = sle.stock_value

            sle.update({"qty_after_transaction": actual_qty,
                       "stock_value": stock_value})

        sle.update({"in_qty": max(sle.actual_qty, 0),
                   "out_qty": min(sle.actual_qty, 0)})

        if sle.serial_no:
            update_available_serial_nos(available_serial_nos, sle)

        if sle.actual_qty:
            sle["in_out_rate"] = flt(
                sle.stock_value_difference / sle.actual_qty, precision)

        elif sle.voucher_type == "Stock Reconciliation":
            sle["in_out_rate"] = sle.valuation_rate

        data.append(sle)

        if include_uom:
            conversion_factors.append(item_detail.conversion_factor)

    update_included_uom_in_report(
        columns, data, include_uom, conversion_factors)
    return columns, data


def get_pivot_data(filters=None):
    """
    تحويل الـ warehouse من صفوف لأعمدة
    باقي الأعمدة تظهر عادي زي الـ original
    """
    # نجيب الـ data العادية
    items = get_items(filters)
    sl_entries = get_stock_ledger_entries(filters, items)

    if not sl_entries:
        return [], []

    item_details = get_item_details(items, sl_entries, None)

    # نجمع كل الـ warehouses الموجودة
    warehouses = set()
    for sle in sl_entries:
        if sle.get('warehouse'):
            warehouses.add(sle.get('warehouse'))

    warehouses = sorted(list(warehouses))

    if not warehouses:
        return [], []

    # نبني structure للـ pivot
    # {unique_key: {data, warehouses: {wh: balance}}}
    pivot_structure = {}

    for sle in sl_entries:
        # نعمل key فريد لكل transaction
        key = f"{sle.get('date')}_{sle.get('item_code')}_{sle.get('voucher_no')}_{sle.get('voucher_type')}"

        if key not in pivot_structure:
            item_detail = item_details.get(sle.get('item_code'), {})

            # نحفظ كل البيانات
            pivot_structure[key] = {
                'date': sle.get('date'),
                'item_code': sle.get('item_code'),
                'item_name': item_detail.get('item_name', ''),
                'stock_uom': item_detail.get('stock_uom', ''),
                'in_qty': flt(sle.get('actual_qty', 0) if sle.get('actual_qty', 0) > 0 else 0, 2),
                'out_qty': flt(sle.get('actual_qty', 0) if sle.get('actual_qty', 0) < 0 else 0, 2),
                'item_group': item_detail.get('item_group', ''),
                'brand': item_detail.get('brand', ''),
                'description': item_detail.get('description', ''),
                'incoming_rate': flt(sle.get('incoming_rate', 0), 2),
                'valuation_rate': flt(sle.get('valuation_rate', 0), 2),
                'stock_value': flt(sle.get('stock_value', 0), 2),
                'stock_value_difference': flt(sle.get('stock_value_difference', 0), 2),
                'voucher_type': sle.get('voucher_type'),
                'voucher_no': sle.get('voucher_no'),
                'batch_no': sle.get('batch_no'),
                'serial_no': sle.get('serial_no'),
                'project': sle.get('project'),
                'company': sle.get('company'),
                'warehouses': {}
            }

        # نضيف الـ balance qty للـ warehouse
        warehouse = sle.get('warehouse')
        if warehouse:
            pivot_structure[key]['warehouses'][warehouse] = flt(
                sle.get('qty_after_transaction', 0), 2)

    # نبني الأعمدة - كل حاجة زي الـ original
    pivot_columns = [
        {"label": _("Date"), "fieldname": "date",
         "fieldtype": "Datetime", "width": 150},
        {"label": _("Item"), "fieldname": "item_code",
         "fieldtype": "Link", "options": "Item", "width": 100},
        {"label": _("Item Name"), "fieldname": "item_name", "width": 100},
        {"label": _("Stock UOM"), "fieldname": "stock_uom",
         "fieldtype": "Link", "options": "UOM", "width": 90},
    ]

    # نضيف inventory dimensions لو موجودة
    for dimension in get_inventory_dimensions():
        pivot_columns.append({
            "label": _(dimension.doctype),
            "fieldname": dimension.fieldname,
            "fieldtype": "Link",
            "options": dimension.doctype,
            "width": 110,
        })

    pivot_columns.extend([
        {"label": _("In Qty"), "fieldname": "in_qty",
         "fieldtype": "Float", "width": 80, "convertible": "qty"},
        {"label": _("Out Qty"), "fieldname": "out_qty",
         "fieldtype": "Float", "width": 80, "convertible": "qty"},
        {
            "label": _("Stock on Hand"),
            "fieldname": "stock_on_hand",
            "fieldtype": "Int",
            "width": 120
        }

    ])

    # نضيف عمود لكل warehouse (هنا الفرق - Balance Qty لكل warehouse)
    warehouse_fieldnames = {}
    for warehouse in warehouses:
        # نعمل fieldname آمن
        safe_fieldname = "wh_" + "".join(
            c if c.isalnum() else '_'
            for c in warehouse
        )[:60]

        warehouse_fieldnames[warehouse] = safe_fieldname

        pivot_columns.append({
            "label": f"{warehouse}",  # اسم الـ warehouse كعنوان العمود
            "fieldname": safe_fieldname,
            "fieldtype": "Float",
            "width": 110
        })

    # باقي الأعمدة زي الـ original
    pivot_columns.extend([
        {"label": _("Item Group"), "fieldname": "item_group",
         "fieldtype": "Link", "options": "Item Group", "width": 100},
        {"label": _("Brand"), "fieldname": "brand",
         "fieldtype": "Link", "options": "Brand", "width": 100},
        {"label": _("Description"), "fieldname": "description", "width": 200},
        {"label": _("Incoming Rate"), "fieldname": "incoming_rate", "fieldtype": "Currency", "width": 110,
         "options": "Company:company:default_currency", "convertible": "rate"},
        {"label": _("Avg Rate (Balance Stock)"), "fieldname": "valuation_rate",
         "fieldtype": filters.get('valuation_field_type', 'Currency'), "width": 180,
         "options": "Company:company:default_currency" if filters.get('valuation_field_type') == "Currency" else None,
         "convertible": "rate"},
        {"label": _("Balance Value"), "fieldname": "stock_value", "fieldtype": "Currency", "width": 110,
         "options": "Company:company:default_currency"},
        {"label": _("Value Change"), "fieldname": "stock_value_difference", "fieldtype": "Currency", "width": 110,
         "options": "Company:company:default_currency"},
        {"label": _("Voucher Type"),
         "fieldname": "voucher_type", "width": 110},
        {"label": _("Voucher #"), "fieldname": "voucher_no",
         "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 100},
        {"label": _("Batch"), "fieldname": "batch_no",
         "fieldtype": "Link", "options": "Batch", "width": 100},
        {"label": _("Serial No"), "fieldname": "serial_no",
         "fieldtype": "Link", "options": "Serial No", "width": 100},
        {"label": _("Project"), "fieldname": "project",
         "fieldtype": "Link", "options": "Project", "width": 100},
        {"label": _("Company"), "fieldname": "company",
         "fieldtype": "Link", "options": "Company", "width": 110},
    ])

    # نبني الصفوف
    pivot_rows = []

    for key in sorted(pivot_structure.keys()):
        entry = pivot_structure[key]

        row = {
            'date': entry['date'],
            'item_code': entry['item_code'],
            'item_name': entry['item_name'],
            'stock_uom': entry['stock_uom'],
            'in_qty': entry['in_qty'],
            'out_qty': entry['out_qty'],
            'item_group': entry['item_group'],
            'brand': entry['brand'],
            'description': entry['description'],
            'incoming_rate': entry['incoming_rate'],
            'valuation_rate': entry['valuation_rate'],
            'stock_value': entry['stock_value'],
            'stock_value_difference': entry['stock_value_difference'],
            'voucher_type': entry['voucher_type'],
            'voucher_no': entry['voucher_no'],
            'batch_no': entry['batch_no'],
            'serial_no': entry['serial_no'],
            'project': entry['project'],
            'company': entry['company'],
        }

        # نضيف الـ balance qty لكل warehouse
        for warehouse in warehouses:
            fieldname = warehouse_fieldnames[warehouse]
            row[fieldname] = entry['warehouses'].get(warehouse, 0)

        # نحسب Stock on Hand (مجموع كل المخازن)
        stock_on_hand = sum(entry['warehouses'].values())
        row['stock_on_hand'] = int(stock_on_hand)

        pivot_rows.append(row)

    return pivot_columns, pivot_rows


def get_segregated_bundle_entries(sle, bundle_details, batch_balance_dict, filters):
    segregated_entries = []
    qty_before_transaction = sle.qty_after_transaction - sle.actual_qty
    stock_value_before_transaction = sle.stock_value - sle.stock_value_difference

    for row in bundle_details:
        new_sle = copy.deepcopy(sle)
        new_sle.update(row)
        new_sle.update(
            {
                "in_out_rate": flt(new_sle.stock_value_difference / row.qty) if row.qty else 0,
                "in_qty": row.qty if row.qty > 0 else 0,
                "out_qty": row.qty if row.qty < 0 else 0,
                "qty_after_transaction": qty_before_transaction + row.qty,
                "stock_value": stock_value_before_transaction + new_sle.stock_value_difference,
                "incoming_rate": row.incoming_rate if row.qty > 0 else 0,
            }
        )

        if filters.get("batch_no") and row.batch_no:
            if not batch_balance_dict.get(row.batch_no):
                batch_balance_dict[row.batch_no] = [0, 0]

            batch_balance_dict[row.batch_no][0] += row.qty
            batch_balance_dict[row.batch_no][1] += row.stock_value_difference

            new_sle.update(
                {
                    "qty_after_transaction": batch_balance_dict[row.batch_no][0],
                    "stock_value": batch_balance_dict[row.batch_no][1],
                }
            )

        qty_before_transaction += row.qty
        stock_value_before_transaction += new_sle.stock_value_difference

        new_sle.valuation_rate = (
            stock_value_before_transaction /
            qty_before_transaction if qty_before_transaction else 0
        )

        segregated_entries.append(new_sle)

    return segregated_entries


def get_serial_batch_bundle_details(sl_entries, filters=None):
    bundle_details = []
    for sle in sl_entries:
        if sle.serial_and_batch_bundle:
            bundle_details.append(sle.serial_and_batch_bundle)

    if not bundle_details:
        return frappe._dict({})

    query_filers = {"parent": ("in", bundle_details)}
    if filters.get("batch_no"):
        query_filers["batch_no"] = filters.batch_no

    _bundle_details = frappe._dict({})
    batch_entries = frappe.get_all(
        "Serial and Batch Entry",
        filters=query_filers,
        fields=["parent", "qty", "incoming_rate",
                "stock_value_difference", "batch_no", "serial_no"],
        order_by="parent, idx",
    )
    for entry in batch_entries:
        _bundle_details.setdefault(entry.parent, []).append(entry)

    return _bundle_details


def update_available_serial_nos(available_serial_nos, sle):
    serial_nos = get_serial_nos(sle.serial_no)
    key = (sle.item_code, sle.warehouse)
    if key not in available_serial_nos:
        stock_balance = get_stock_balance_for(
            sle.item_code, sle.warehouse, sle.posting_date, sle.posting_time
        )
        serials = get_serial_nos(
            stock_balance["serial_nos"]) if stock_balance["serial_nos"] else []
        available_serial_nos.setdefault(key, serials)

    existing_serial_no = available_serial_nos[key]
    for sn in serial_nos:
        if sle.actual_qty > 0:
            if sn in existing_serial_no:
                existing_serial_no.remove(sn)
            else:
                existing_serial_no.append(sn)
        else:
            if sn in existing_serial_no:
                existing_serial_no.remove(sn)
            else:
                existing_serial_no.append(sn)

    sle.balance_serial_no = "\n".join(existing_serial_no)


def get_columns(filters):
    columns = [
        {"label": _("Date"), "fieldname": "date",
         "fieldtype": "Datetime", "width": 150},
        {
            "label": _("Item"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 100,
        },
        {"label": _("Item Name"), "fieldname": "item_name", "width": 100},
        {
            "label": _("Stock UOM"),
            "fieldname": "stock_uom",
            "fieldtype": "Link",
            "options": "UOM",
            "width": 90,
        },
    ]

    for dimension in get_inventory_dimensions():
        columns.append(
            {
                "label": _(dimension.doctype),
                "fieldname": dimension.fieldname,
                "fieldtype": "Link",
                "options": dimension.doctype,
                "width": 110,
            }
        )

    columns.extend(
        [
            {
                "label": _("In Qty"),
                "fieldname": "in_qty",
                "fieldtype": "Float",
                "width": 80,
                "convertible": "qty",
            },
            {
                "label": _("Out Qty"),
                "fieldname": "out_qty",
                "fieldtype": "Float",
                "width": 80,
                "convertible": "qty",
            },
            {
                "label": _("Balance Qty"),
                "fieldname": "qty_after_transaction",
                "fieldtype": "Float",
                "width": 100,
                "convertible": "qty",
            },
            {
                "label": _("Warehouse"),
                "fieldname": "warehouse",
                "fieldtype": "Link",
                "options": "Warehouse",
                "width": 150,
            },
            {
                "label": _("Item Group"),
                "fieldname": "item_group",
                "fieldtype": "Link",
                "options": "Item Group",
                "width": 100,
            },
            {
                "label": _("Brand"),
                "fieldname": "brand",
                "fieldtype": "Link",
                "options": "Brand",
                "width": 100,
            },
            {"label": _("Description"),
             "fieldname": "description", "width": 200},
            {
                "label": _("Incoming Rate"),
                "fieldname": "incoming_rate",
                "fieldtype": "Currency",
                "width": 110,
                "options": "Company:company:default_currency",
                "convertible": "rate",
            },
            {
                "label": _("Avg Rate (Balance Stock)"),
                "fieldname": "valuation_rate",
                "fieldtype": filters.valuation_field_type,
                "width": 180,
                "options": "Company:company:default_currency"
                if filters.valuation_field_type == "Currency"
                else None,
                "convertible": "rate",
            },
            {
                "label": _("Valuation Rate"),
                "fieldname": "in_out_rate",
                "fieldtype": filters.valuation_field_type,
                "width": 140,
                "options": "Company:company:default_currency"
                if filters.valuation_field_type == "Currency"
                else None,
                "convertible": "rate",
            },
            {
                "label": _("Balance Value"),
                "fieldname": "stock_value",
                "fieldtype": "Currency",
                "width": 110,
                "options": "Company:company:default_currency",
            },
            {
                "label": _("Value Change"),
                "fieldname": "stock_value_difference",
                "fieldtype": "Currency",
                "width": 110,
                "options": "Company:company:default_currency",
            },
            {"label": _("Voucher Type"),
             "fieldname": "voucher_type", "width": 110},
            {
                "label": _("Voucher #"),
                "fieldname": "voucher_no",
                "fieldtype": "Dynamic Link",
                "options": "voucher_type",
                "width": 100,
            },
            {
                "label": _("Batch"),
                "fieldname": "batch_no",
                "fieldtype": "Link",
                "options": "Batch",
                "width": 100,
            },
            {
                "label": _("Serial No"),
                "fieldname": "serial_no",
                "fieldtype": "Link",
                "options": "Serial No",
                "width": 100,
            },
            {
                "label": _("Serial and Batch Bundle"),
                "fieldname": "serial_and_batch_bundle",
                "fieldtype": "Link",
                "options": "Serial and Batch Bundle",
                "width": 100,
            },
            {
                "label": _("Project"),
                "fieldname": "project",
                "fieldtype": "Link",
                "options": "Project",
                "width": 100,
            },
            {
                "label": _("Company"),
                "fieldname": "company",
                "fieldtype": "Link",
                "options": "Company",
                "width": 110,
            },
        ]
    )

    return columns


def get_stock_ledger_entries(filters, items):
    from_date = get_datetime(filters.from_date + " 00:00:00")
    to_date = get_datetime(filters.to_date + " 23:59:59")

    sle = frappe.qb.DocType("Stock Ledger Entry")
    query = (
        frappe.qb.from_(sle)
        .select(
            sle.item_code,
            sle.posting_datetime.as_("date"),
            sle.warehouse,
            sle.posting_date,
            sle.posting_time,
            sle.actual_qty,
            sle.incoming_rate,
            sle.valuation_rate,
            sle.company,
            sle.voucher_type,
            sle.qty_after_transaction,
            sle.stock_value_difference,
            sle.serial_and_batch_bundle,
            sle.voucher_no,
            sle.stock_value,
            sle.batch_no,
            sle.serial_no,
            sle.project,
        )
        .where((sle.docstatus < 2) & (sle.is_cancelled == 0) & (sle.posting_datetime[from_date:to_date]))
        .orderby(sle.posting_datetime)
        .orderby(sle.creation)
    )

    inventory_dimension_fields = get_inventory_dimension_fields()
    if inventory_dimension_fields:
        for fieldname in inventory_dimension_fields:
            query = query.select(fieldname)
            if fieldname in filters and filters.get(fieldname):
                query = query.where(
                    sle[fieldname].isin(filters.get(fieldname)))

    if items:
        query = query.where(sle.item_code.isin(items))

    for field in ["voucher_no", "project", "company"]:
        if filters.get(field) and field not in inventory_dimension_fields:
            query = query.where(sle[field] == filters.get(field))

    if filters.get("batch_no"):
        bundles = get_serial_and_batch_bundles(filters)

        if bundles:
            query = query.where(
                (sle.serial_and_batch_bundle.isin(bundles)) | (
                    sle.batch_no == filters.batch_no)
            )
        else:
            query = query.where(sle.batch_no == filters.batch_no)

    query = apply_warehouse_filter(query, sle, filters)

    return query.run(as_dict=True)


def get_serial_and_batch_bundles(filters):
    SBB = frappe.qb.DocType("Serial and Batch Bundle")
    SBE = frappe.qb.DocType("Serial and Batch Entry")

    query = (
        frappe.qb.from_(SBE)
        .inner_join(SBB)
        .on(SBE.parent == SBB.name)
        .select(SBE.parent)
        .where(
            (SBB.docstatus == 1)
            & (SBB.has_batch_no == 1)
            & (SBB.voucher_no.notnull())
            & (SBE.batch_no == filters.batch_no)
        )
    )

    return query.run(pluck=SBE.parent)


def get_inventory_dimension_fields():
    return [dimension.fieldname for dimension in get_inventory_dimensions()]


def get_items(filters):
    item = frappe.qb.DocType("Item")
    query = frappe.qb.from_(item).select(item.name)
    conditions = []

    if item_code := filters.get("item_code"):
        conditions.append(item.name == item_code)
    else:
        if brand := filters.get("brand"):
            conditions.append(item.brand == brand)
        if item_group := filters.get("item_group"):
            if condition := get_item_group_condition(item_group, item):
                conditions.append(condition)

    items = []
    if conditions:
        for condition in conditions:
            query = query.where(condition)
        items = [r[0] for r in query.run()]

    return items


def get_item_details(items, sl_entries, include_uom):
    item_details = {}
    if not items:
        items = list(set(d.item_code for d in sl_entries))

    if not items:
        return item_details

    item = frappe.qb.DocType("Item")
    query = (
        frappe.qb.from_(item)
        .select(item.name, item.item_name, item.description, item.item_group, item.brand, item.stock_uom)
        .where(item.name.isin(items))
    )

    if include_uom:
        ucd = frappe.qb.DocType("UOM Conversion Detail")
        query = (
            query.left_join(ucd)
            .on((ucd.parent == item.name) & (ucd.uom == include_uom))
            .select(ucd.conversion_factor)
        )

    res = query.run(as_dict=True)

    for item in res:
        item_details.setdefault(item.name, item)

    return item_details


def get_sle_conditions(filters):
    conditions = []
    if filters.get("warehouse"):
        warehouse_condition = get_warehouse_condition(filters.get("warehouse"))
        if warehouse_condition:
            conditions.append(warehouse_condition)
    if filters.get("voucher_no"):
        conditions.append("voucher_no=%(voucher_no)s")
    if filters.get("batch_no"):
        conditions.append("batch_no=%(batch_no)s")
    if filters.get("project"):
        conditions.append("project=%(project)s")

    for dimension in get_inventory_dimensions():
        if filters.get(dimension.fieldname):
            conditions.append(
                f"{dimension.fieldname} in %({dimension.fieldname})s")

    return "and {}".format(" and ".join(conditions)) if conditions else ""


def get_opening_balance_from_batch(filters, columns, sl_entries):
    query_filters = {
        "batch_no": filters.batch_no,
        "docstatus": 1,
        "is_cancelled": 0,
        "posting_date": ("<", filters.from_date),
        "company": filters.company,
    }

    for fields in ["item_code", "warehouse"]:
        if filters.get(fields):
            query_filters[fields] = filters.get(fields)

    opening_data = frappe.get_all(
        "Stock Ledger Entry",
        fields=["sum(actual_qty) as qty_after_transaction",
                "sum(stock_value_difference) as stock_value"],
        filters=query_filters,
    )[0]

    for field in ["qty_after_transaction", "stock_value", "valuation_rate"]:
        if opening_data.get(field) is None:
            opening_data[field] = 0.0

    table = frappe.qb.DocType("Stock Ledger Entry")
    sabb_table = frappe.qb.DocType("Serial and Batch Entry")
    query = (
        frappe.qb.from_(table)
        .inner_join(sabb_table)
        .on(table.serial_and_batch_bundle == sabb_table.parent)
        .select(
            Sum(sabb_table.qty).as_("qty"),
            Sum(sabb_table.stock_value_difference).as_("stock_value"),
        )
        .where(
            (sabb_table.batch_no == filters.batch_no)
            & (sabb_table.docstatus == 1)
            & (table.posting_date < filters.from_date)
            & (table.is_cancelled == 0)
        )
    )

    for field in ["item_code", "warehouse", "company"]:
        if filters.get(field):
            query = query.where(table[field] == filters.get(field))

    bundle_data = query.run(as_dict=True)

    if bundle_data:
        opening_data.qty_after_transaction += flt(bundle_data[0].qty)
        opening_data.stock_value += flt(bundle_data[0].stock_value)
        if opening_data.qty_after_transaction:
            opening_data.valuation_rate = flt(opening_data.stock_value) / flt(
                opening_data.qty_after_transaction
            )

    return {
        "item_code": _("'Opening'"),
        "qty_after_transaction": opening_data.qty_after_transaction,
        "valuation_rate": opening_data.valuation_rate,
        "stock_value": opening_data.stock_value,
    }


def get_opening_balance(filters, columns, sl_entries):
    if not (filters.item_code and filters.warehouse and filters.from_date):
        return

    from erpnext.stock.stock_ledger import get_previous_sle

    last_entry = get_previous_sle(
        {
            "item_code": filters.item_code,
            "warehouse_condition": get_warehouse_condition(filters.warehouse),
            "posting_date": filters.from_date,
            "posting_time": "00:00:00",
        }
    )

    # check if any SLEs are actually Opening Stock Reconciliation
    for sle in list(sl_entries):
        if (
                sle.get("voucher_type") == "Stock Reconciliation"
                and sle.posting_date == filters.from_date
                and frappe.db.get_value("Stock Reconciliation", sle.voucher_no, "purpose") == "Opening Stock"
        ):
            last_entry = sle
            sl_entries.remove(sle)

    row = {
        "item_code": _("'Opening'"),
        "qty_after_transaction": last_entry.get("qty_after_transaction", 0),
        "valuation_rate": last_entry.get("valuation_rate", 0),
        "stock_value": last_entry.get("stock_value", 0),
    }

    return row


def get_warehouse_condition(warehouse):
    warehouse_details = frappe.db.get_value(
        "Warehouse", warehouse, ["lft", "rgt"], as_dict=1)
    if warehouse_details:
        return f" exists (select name from `tabWarehouse` wh \
			where wh.lft >= {warehouse_details.lft} and wh.rgt <= {warehouse_details.rgt} and warehouse = wh.name)"

    return ""


def get_item_group_condition(item_group, item_table=None):
    item_group_details = frappe.db.get_value(
        "Item Group", item_group, ["lft", "rgt"], as_dict=1)
    if item_group_details:
        if item_table:
            ig = frappe.qb.DocType("Item Group")
            return item_table.item_group.isin(
                frappe.qb.from_(ig)
                .select(ig.name)
                .where(
                    (ig.lft >= item_group_details.lft)
                    & (ig.rgt <= item_group_details.rgt)
                    & (item_table.item_group == ig.name)
                )
            )
        else:
            return f"item.item_group in (select ig.name from `tabItem Group` ig \
				where ig.lft >= {item_group_details.lft} and ig.rgt <= {item_group_details.rgt} and item.item_group = ig.name)"


def check_inventory_dimension_filters_applied(filters) -> bool:
    for dimension in get_inventory_dimensions():
        if dimension.fieldname in filters and filters.get(dimension.fieldname):
            return True

    return False
