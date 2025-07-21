import erpnext.controllers.status_updater
import erpnext.stock.utils
import erpnext.stock.stock_ledger
import frappe


def no_validate_actual_qty(self, sn_doc):
    # Disabled all core validations in this method as per user request
    pass


# Monkey patch for make_sl_entries to force incoming_rate from PR
original_make_sl_entries = erpnext.stock.stock_ledger.make_sl_entries


def custom_make_sl_entries(sl_entries, *args, **kwargs):
    for entry in sl_entries:
        if entry.get('voucher_type') == 'Purchase Receipt':
            pr_item = frappe.db.get_value(
                "Purchase Receipt Item",
                {
                    "parent": entry.get("voucher_no"),
                    "item_code": entry.get("item_code"),
                    "batch_no": entry.get("batch_no") if entry.get("batch_no") else ["!=", ""]
                },
                "base_rate"
            )
            if pr_item:
                # Set to PR base_rate (company currency)
                entry['incoming_rate'] = pr_item
                # Force valuation_rate to match incoming_rate
                entry['valuation_rate'] = pr_item
    return original_make_sl_entries(sl_entries, *args, **kwargs)


def apply_monkey_patches():
    from erpnext.stock.serial_batch_bundle import SerialBatchBundle
    global original_get_incoming_rate
    original_get_incoming_rate = erpnext.stock.utils.get_incoming_rate
    erpnext.stock.stock_ledger.make_sl_entries = custom_make_sl_entries
    SerialBatchBundle.validate_actual_qty = no_validate_actual_qty


def no_op_limits_crossed_error(self, args, item, qty_or_amount):
    # Bypass the over limit validation (do nothing)
    pass


erpnext.controllers.status_updater.StatusUpdater.limits_crossed_error = no_op_limits_crossed_error
