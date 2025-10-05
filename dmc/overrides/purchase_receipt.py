from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from frappe.utils import flt, money_in_words
import frappe
from frappe import _


class CustomPurchaseReceipt(PurchaseReceipt):

    def on_submit(self):
    
        self.set_in_words()
  

    def after_save(self):
      
        self.set_in_words()


    def set_in_words(self):
        """Set amount in words"""
        if self.rounded_total:
            self.in_words = money_in_words(self.rounded_total, self.currency)
        elif self.grand_total:
            self.in_words = money_in_words(self.grand_total, self.currency)

        # Always set base_in_words
        if self.base_rounded_total:
            self.base_in_words = money_in_words(
                self.base_rounded_total, self.company_currency)
        elif self.base_grand_total:
            self.base_in_words = money_in_words(
                self.base_grand_total, self.company_currency)

