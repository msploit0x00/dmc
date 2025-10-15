import frappe
from frappe import _
from frappe.utils import flt
from frappe.exceptions import ValidationError
from erpnext.controllers.buying_controller import BuyingController


# نفس الـ Exception اللي بيستخدمه ERPNext في buying_controller
class QtyMismatchError(ValidationError):
    pass


class CustomBuyingController(BuyingController):
    """
    ✅ Custom override for BuyingController
    Allows received_qty <= accepted_qty + rejected_qty
    Throws error only if received_qty > accepted_qty + rejected_qty
    """

    def validate_accepted_rejected_qty(self):
        for d in self.get("items"):
            self.validate_negative_quantity(
                d, ["received_qty", "qty", "rejected_qty"])

            # لو مفيش received_qty نحسبه افتراضيًا
            if not flt(d.received_qty) and (flt(d.qty) or flt(d.rejected_qty)):
                d.received_qty = flt(d.qty) + flt(d.rejected_qty)

            total_qty = flt(d.qty) + flt(d.rejected_qty)
            received = flt(d.received_qty, d.precision("received_qty"))

            # ✅ لو المستلم <= المقبول + المرفوض --> تمام
            if received <= total_qty:
                continue

            # ❌ لو المستلم أكبر --> ارمي خطأ
            message = _(
                "Row #{0}: Received Qty cannot be greater than Accepted + Rejected Qty for Item {1}"
            ).format(d.idx, d.item_code)
            frappe.throw(msg=message, title=_(
                "Qty Mismatch"), exc=QtyMismatchError)
