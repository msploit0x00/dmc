# your_custom_app/overrides/stock_ledger.py
from erpnext.stock.stock_ledger import StockLedger
from frappe.utils import flt
import frappe


class CustomStockLedger(StockLedger):

    def process_sle(self, sle):
        self.wh_data = self.data[sle.warehouse]
        self.validate_previous_sle_qty(sle)
        self.affected_transactions.add((sle.voucher_type, sle.voucher_no))
        super().process_sle(sle)  # Call original

        # Custom logic only for Purchase Receipt
        if sle.voucher_type == "Purchase Receipt" and not getattr(self, "via_landed_cost_voucher", False):
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
