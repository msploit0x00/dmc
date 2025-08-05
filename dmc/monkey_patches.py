import erpnext.controllers.status_updater
import erpnext.stock.utils
import erpnext.stock.stock_ledger
import frappe
from frappe.utils import flt


def no_validate_actual_qty(self, sn_doc):
    # Disabled all core validations in this method as per user request
    pass


# Monkey patch for make_sl_entries to force incoming_rate from PR
original_make_sl_entries = erpnext.stock.stock_ledger.make_sl_entries


def custom_make_sl_entries(sl_entries, *args, **kwargs):
    for entry in sl_entries:
        if entry.get('voucher_type') == 'Purchase Receipt':
            filters = {
                "parent": entry.get("voucher_no"),
                "item_code": entry.get("item_code"),
            }
            if entry.get("batch_no"):
                filters["batch_no"] = entry.get("batch_no")
            pr_base_rate = frappe.db.get_value(
                "Purchase Receipt Item", filters, "base_rate")
            if pr_base_rate:
                entry['valuation_rate'] = pr_base_rate
                entry['incoming_rate'] = pr_base_rate
    return original_make_sl_entries(sl_entries, *args, **kwargs)


def apply_monkey_patches():

    from erpnext.stock.serial_batch_bundle import SerialBatchBundle
    global original_get_incoming_rate
    original_get_incoming_rate = erpnext.stock.utils.get_incoming_rate
    erpnext.stock.stock_ledger.make_sl_entries = custom_make_sl_entries
    SerialBatchBundle.validate_actual_qty = no_validate_actual_qty

    from erpnext.stock.stock_ledger import update_entries_after

    def custom_get_moving_average_values(self, sle):
        pr_base_rate = None
        if sle.voucher_type == "Purchase Receipt":
            pr_base_rate = frappe.db.get_value(
                "Purchase Receipt Item",
                {
                    "parent": sle.voucher_no,
                    "item_code": sle.item_code,
                    "batch_no": sle.batch_no if sle.batch_no else ["!=", ""]
                },
                "base_rate"
            )
        if pr_base_rate:
            self.wh_data.valuation_rate = pr_base_rate
            sle.incoming_rate = pr_base_rate
        else:
            self.wh_data.valuation_rate = sle.incoming_rate

    update_entries_after.get_moving_average_values = custom_get_moving_average_values

    original_process_sle = update_entries_after.process_sle

    def custom_process_sle(self, sle):
        # Call the original up to the point of SLE update, but override for PR
        self.wh_data = self.data[sle.warehouse]
        self.validate_previous_sle_qty(sle)
        self.affected_transactions.add((sle.voucher_type, sle.voucher_no))
        original_process_sle(self, sle)
        # Only override for original PR, not for LCV reposts
        if (
            sle.voucher_type == "Purchase Receipt"
            and not getattr(self, "via_landed_cost_voucher", False)
        ):
            pr_base_rate = frappe.db.get_value(
                "Purchase Receipt Item",
                {
                    "parent": sle.voucher_no,
                    "item_code": sle.item_code,
                    "batch_no": sle.batch_no if sle.batch_no else ["!=", ""]
                },
                "base_rate"
            )
            if pr_base_rate:
                sle.incoming_rate = pr_base_rate
                sle.valuation_rate = pr_base_rate
                sle.stock_value_difference = flt(
                    sle.actual_qty) * flt(pr_base_rate)
                frappe.db.set_value("Stock Ledger Entry", sle.name, {
                    "incoming_rate": pr_base_rate,
                    "valuation_rate": pr_base_rate,
                    "stock_value_difference": flt(sle.actual_qty) * flt(pr_base_rate)
                })

    update_entries_after.process_sle = custom_process_sle


def no_op_limits_crossed_error(self, args, item, qty_or_amount):
    # Bypass the over limit validation (do nothing)
    pass


erpnext.controllers.status_updater.StatusUpdater.limits_crossed_error = no_op_limits_crossed_error
