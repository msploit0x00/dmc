from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from frappe.utils import flt, money_in_words
import frappe
from frappe import _


class CustomPurchaseReceipt(PurchaseReceipt):

    def validate_accepted_rejected_qty(self):
        """
        Modified validation: Allow received_qty <= accepted_qty
        Only throw error if received_qty > accepted_qty
        """
        for d in self.get("items"):
            self.validate_negative_quantity(
                d, ["received_qty", "qty", "rejected_qty"])

            if not flt(d.received_qty) and (flt(d.qty) or flt(d.rejected_qty)):
                d.received_qty = flt(d.qty) + flt(d.rejected_qty)

            # ✅ التعديل: بدل != حطينا >
            val = flt(d.qty) + flt(d.rejected_qty)
            if flt(d.received_qty, d.precision("received_qty")) > flt(val, d.precision("received_qty")):
                message = _(
                    "Row #{0}: Received Qty ({1}) cannot exceed Accepted + Rejected Qty ({2}) for Item {3}"
                ).format(d.idx, d.received_qty, val, d.item_code)
                frappe.throw(msg=message, title=_("Quantity Exceeded"))

    # def on_submit(self):

    #     self.set_in_words()

    # def after_save(self):

    #     self.set_in_words()
