from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from frappe.utils import flt, money_in_words
import frappe
from frappe import _


class CustomPurchaseReceipt(PurchaseReceipt):
    def validate_with_previous_doc(self):
        pass

    def validate(self):
        if self.custom_purchase_invoice_name:
            try:
                pinv = frappe.get_doc('Purchase Invoice',
                                      self.custom_purchase_invoice_name)

                # Copy taxes
                self.taxes = []
                for tax in pinv.taxes:
                    self.append('taxes', tax.as_dict(copy=True))

                # Copy items
                for item in self.items:
                    pi_item = next(
                        (x for x in pinv.items if x.item_code == item.item_code), None)
                    if pi_item:
                        original_qty = item.qty
                        original_uom = item.uom
                        original_warehouse = item.warehouse
                        for key, value in pi_item.as_dict().items():
                            if key not in ['qty', 'uom', 'warehouse', 'name', 'doctype', 'parent', 'parentfield', 'parenttype']:
                                setattr(item, key, value)
                        item.qty = original_qty
                        item.uom = original_uom
                        item.warehouse = original_warehouse

                # Copy all totals
                for field in [
                    'total', 'net_total', 'base_total', 'base_net_total',
                    'grand_total', 'rounded_total', 'base_grand_total', 'base_rounded_total'
                ]:
                    setattr(self, field, getattr(pinv, field))

                self.base_tax_withholding_net_total = 0
                currency = getattr(self, "company_currency", None) or getattr(
                    self, "currency", None) or "EGP"
                self.base_in_words = money_in_words(
                    self.base_rounded_total, currency)

            except Exception as e:
                frappe.log_error(
                    f"Error updating from purchase invoice: {str(e)}", "Purchase Receipt Update Error")

        # Always update total_qty from items using received_stock_qty
        self.total_qty = sum(flt(item.received_stock_qty)
                             for item in self.items)
        self.db_set('total_qty', self.total_qty)

        # Calculate totals if not set from purchase invoice
        if not self.custom_purchase_invoice_name:
            self.calculate_taxes_and_totals()
            self.set_rounded_total()
            self.set_in_words()

    def on_submit(self):
        self.validate()
        # Update total_qty using received_stock_qty
        self.total_qty = sum(flt(item.received_stock_qty)
                             for item in self.items)
        self.db_set('total_qty', self.total_qty)
        self.db_set('base_tax_withholding_net_total', 0)

    def after_save(self):
        # Update total_qty using received_stock_qty
        self.total_qty = sum(flt(item.received_stock_qty)
                             for item in self.items)
        self.db_set('total_qty', self.total_qty)
        # Clear the field after saving and persist to DB
        self.base_tax_withholding_net_total = 0
        self.db_set('base_tax_withholding_net_total', 0)

    def update_total_qty(self):
        total = sum(flt(d.received_stock_qty) for d in self.items)
        self.total_qty = total
        self.db_set('total_qty', total)

    def update_total_amount(self):
        total = sum(flt(d.base_amount) for d in self.items)
        self.base_total = total
        self.db_set('base_total', total)

    def set_rounded_total(self):
        """Calculate and set rounded total"""
        if not self.disable_rounded_total:
            self.rounding_adjustment = flt(
                self.grand_total - self.rounded_total, self.precision("rounding_adjustment"))
            self.rounded_total = flt(
                self.grand_total, self.precision("rounded_total"))
            self.base_rounding_adjustment = flt(
                self.base_grand_total - self.base_rounded_total, self.precision("base_rounding_adjustment"))
            self.base_rounded_total = flt(
                self.base_grand_total, self.precision("base_rounded_total"))

    def set_in_words(self):
        """Set amount in words"""
        if self.grand_total:
            self.in_words = money_in_words(self.rounded_total, self.currency)
            self.base_in_words = money_in_words(
                self.base_rounded_total, self.company_currency)

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

    def fetch_base_amount(self):
        """
        This function loops through items in the Purchase Receipt,
        fetches the matching item from linked Purchase Invoice,
        and sets the base_amount accordingly.
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
                            item.base_amount = matched_item.base_amount
                            # Update total if needed
                            self.base_total = sum(
                                item.base_amount for item in self.items)
                except frappe.DoesNotExistError:
                    frappe.msgprint(
                        f"Purchase Invoice {item.purchase_invoice} not found.")
                except Exception as e:
                    frappe.log_error(frappe.get_traceback(),
                                     "Error in fetch_base_amount")

    def set_base_amount_from_invoice(self):
        # Only run if custom_purchase_invoice_name is set
        if not getattr(self, 'custom_purchase_invoice_name', None):
            return

        try:
            pinv = frappe.get_doc('Purchase Invoice',
                                  self.custom_purchase_invoice_name)
        except frappe.DoesNotExistError:
            frappe.msgprint(_("Purchase Invoice {0} not found.").format(
                self.custom_purchase_invoice_name))
            return

        # Map item_code to Purchase Invoice Item
        pinv_map = {item.item_code: item for item in pinv.items}

        for item in self.items:
            matched = pinv_map.get(item.item_code)
            if matched:
                item.base_rate = matched.base_rate
                item.base_amount = matched.base_amount
                item.stock_uom_rate = matched.stock_uom_rate
                item.net_rate = matched.net_rate
                item.net_amount = matched.net_amount
                item.base_net_rate = matched.base_net_rate
                item.base_net_amount = matched.base_net_amount

        # Force recalculation of totals
        self.calculate_taxes_and_totals()

    def fetch_invoice_data_for_items(self):
        """
        For each item in the Purchase Receipt, fetch matching data from the selected Purchase Invoice
        and update the item's fields.
        """
        if not getattr(self, 'custom_purchase_invoice_name', None):
            return

        try:
            pinv = frappe.get_doc('Purchase Invoice',
                                  self.custom_purchase_invoice_name)
        except frappe.DoesNotExistError:
            frappe.msgprint(_("Purchase Invoice {0} not found.").format(
                self.custom_purchase_invoice_name))
            return

        if not pinv.items or not self.items:
            return

        for item in self.items:
            matched = next(
                (pi_item for pi_item in pinv.items if pi_item.item_code == item.item_code), None)
            if matched:
                item.base_rate = matched.base_rate
                item.base_amount = matched.base_amount
                item.stock_uom_rate = matched.stock_uom_rate
                item.net_rate = matched.net_rate
                item.net_amount = matched.net_amount
                item.base_net_rate = matched.base_net_rate
                item.base_net_amount = matched.base_net_amount
