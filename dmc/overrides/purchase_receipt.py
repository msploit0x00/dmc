from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from frappe.utils import flt
import frappe


class CustomPurchaseReceipt(PurchaseReceipt):
    def validate_with_previous_doc(self):

        pass

    def validate(self):
        super().validate()
        self.update_total_qty()
        self.fetch_stock_rate_uom()
        self.update_total_amount()

    def update_total_qty(self):
        total = sum(flt(d.received_stock_qty) for d in self.items)
        self.total_qty = total

    def update_total_amount(self):
        total = sum(flt(d.base_amount) for d in self.items)
        self.base_total = total

    def fetch_stock_rate_uom(self):
        """
        This function loops through `items` in the given document,
        fetches the matching item from linked Purchase Invoice,
        and sets the stock_uom_rate and base_amount accordingly.
        """
        if not self.items:
            frappe.msgprint("No items found in the table.")
            return

        for item in self.items:
            if item.purchase_invoice:
                try:
                    purchase_invoice = frappe.get_doc(
                        "Purchase Invoice", item.purchase_invoice)
                    if purchase_invoice.items:
                        # Find the matching item by item_code
                        matched_item = next(
                            (pi_item for pi_item in purchase_invoice.items if pi_item.item_code == item.item_code), None)

                        if matched_item:
                            item.stock_uom_rate = matched_item.rate
                            item.base_amount = (
                                item.base_rate or 0) * matched_item.rate
                            self.base_total = item
                except frappe.DoesNotExistError:
                    frappe.msgprint(
                        f"Purchase Invoice {item.purchase_invoice} not found.")
                except Exception as e:
                    frappe.log_error(frappe.get_traceback(),
                                     "Error in fetch_stock_rate_uom")
