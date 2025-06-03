from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from frappe.utils import flt


class CustomPurchaseReceipt(PurchaseReceipt):
    def validate_with_previous_doc(self):

        pass

    # def validate(self):
    #     super().validate()
    #     self.total_qty = sum(flt(d.received_stock_qty) for d in self.items)
