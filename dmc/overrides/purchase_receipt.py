from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from frappe.utils import flt, money_in_words
import frappe
from frappe import _


class CustomPurchaseReceipt(PurchaseReceipt):
    def validate_with_previous_doc(self):
        # Disabled all core validations in this method as per user request
        pass

    def validate(self):
        super().validate()
        if self.custom_purchase_invoice_name:
            self.fetch_invoice_data_for_items()
            # Copy taxes and totals as before
            try:
                pinv = frappe.get_doc('Purchase Invoice',
                                      self.custom_purchase_invoice_name)
                self.taxes = []
                for tax in pinv.taxes:
                    self.append('taxes', tax.as_dict(copy=True))
                # Set all totals from invoice
                for field in [
                    'base_total', 'base_rounded_total', 'base_grand_total',
                    'grand_total', 'rounded_total', 'total', 'net_total', 'base_net_total',
                    'grand_total', 'rounded_total', 'base_grand_total', 'base_rounded_total'
                ]:
                    setattr(self, field, getattr(pinv, field))
                self.base_tax_withholding_net_total = 0
                currency = getattr(self, "company_currency", None) or getattr(
                    self, "currency", None) or "EGP"
                self.base_in_words = money_in_words(
                    self.base_rounded_total, currency)
                if hasattr(pinv, 'in_words') and pinv.in_words:
                    self.in_words = pinv.in_words
                if getattr(pinv, "custom_is_landed_cost", 0):
                    self.custom_shipment_order_name = getattr(
                        pinv, "custom_shipment_name_ref", None)

            except Exception as e:
                frappe.log_error(
                    f"Error updating from purchase invoice: {str(e)}", "Purchase Receipt Update Error")
        else:
            self.calculate_taxes_and_totals()
            self.set_rounded_total()
            self.set_in_words()
        self.total_qty = self.calculate_total_qty()
        self.db_set('total_qty', self.total_qty)
        for item in self.items:
            if not item.received_stock_qty or item.received_stock_qty == 0:
                if item.qty and item.conversion_factor:
                    item.received_stock_qty = flt(
                        item.qty) * flt(item.conversion_factor)

    def on_submit(self):
        super().on_submit()
        if self.custom_purchase_invoice_name:
            self.fetch_invoice_data_for_items()
            try:
                pinv = frappe.get_doc('Purchase Invoice',
                                      self.custom_purchase_invoice_name)
                # Set all totals from invoice
                for field in [
                    'base_total', 'base_rounded_total', 'base_grand_total',
                    'grand_total', 'rounded_total', 'total', 'net_total', 'base_net_total',
                    'grand_total', 'rounded_total', 'base_grand_total', 'base_rounded_total'
                ]:
                    setattr(self, field, getattr(pinv, field))
                self.base_tax_withholding_net_total = 0
                currency = getattr(self, "company_currency", None) or getattr(
                    self, "currency", None) or "EGP"
                self.base_in_words = money_in_words(
                    self.base_rounded_total, currency)
                if hasattr(pinv, 'in_words') and pinv.in_words:
                    self.in_words = pinv.in_words
                self.total_qty = self.calculate_total_qty()
                self.db_set('total_qty', self.total_qty)
                self.db_set('base_tax_withholding_net_total', 0)
                if getattr(pinv, "custom_is_landed_cost", 0):
                    self.custom_shipment_order_name = getattr(
                        pinv, "custom_shipment_name_ref", None)
            except Exception as e:
                frappe.log_error(
                    f"Error in on_submit: {str(e)}", "Purchase Receipt Submit Error")
        else:
            self.calculate_taxes_and_totals()
            self.set_rounded_total()
            self.set_in_words()
            self.total_qty = self.calculate_total_qty()
            self.db_set('total_qty', self.total_qty)
            self.db_set('base_tax_withholding_net_total', 0)

    def after_save(self):
        super().after_save()
        if self.custom_purchase_invoice_name:
            self.fetch_invoice_data_for_items()
            try:
                pinv = frappe.get_doc('Purchase Invoice',
                                      self.custom_purchase_invoice_name)
                # Set all totals from invoice
                for field in [
                    'base_total', 'base_rounded_total', 'base_grand_total',
                    'grand_total', 'rounded_total', 'total', 'net_total', 'base_net_total',
                    'grand_total', 'rounded_total', 'base_grand_total', 'base_rounded_total'
                ]:
                    setattr(self, field, getattr(pinv, field))
                self.base_tax_withholding_net_total = 0
                currency = getattr(self, "company_currency", None) or getattr(
                    self, "currency", None) or "EGP"
                self.base_in_words = money_in_words(
                    self.base_rounded_total, currency)
                if hasattr(pinv, 'in_words') and pinv.in_words:
                    self.in_words = pinv.in_words
                self.total_qty = self.calculate_total_qty()
                self.db_set('total_qty', self.total_qty)
                self.db_set('base_tax_withholding_net_total', 0)
                if getattr(pinv, "custom_is_landed_cost", 0):
                    self.custom_shipment_order_name = getattr(
                        pinv, "custom_shipment_name_ref", None)
            except Exception as e:
                frappe.log_error(
                    f"Error in after_save: {str(e)}", "Purchase Receipt After Save Error")
        else:
            self.calculate_taxes_and_totals()
            self.set_rounded_total()
            self.set_in_words()
            self.total_qty = self.calculate_total_qty()
            self.db_set('total_qty', self.total_qty)
            self.db_set('base_tax_withholding_net_total', 0)

    def update_total_qty(self):
        total = self.calculate_total_qty()
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
        # Try to fetch from linked Purchase Invoice if available
        if getattr(self, 'custom_purchase_invoice_name', None):
            try:
                pinv = frappe.get_doc('Purchase Invoice',
                                      self.custom_purchase_invoice_name)
                if hasattr(pinv, 'in_words') and pinv.in_words:
                    self.in_words = pinv.in_words
                else:
                    # fallback to rounded_total or grand_total
                    if self.rounded_total:
                        self.in_words = money_in_words(
                            self.rounded_total, self.currency)
                    elif self.grand_total:
                        self.in_words = money_in_words(
                            self.grand_total, self.currency)
            except Exception:
                # fallback to rounded_total or grand_total
                if self.rounded_total:
                    self.in_words = money_in_words(
                        self.rounded_total, self.currency)
                elif self.grand_total:
                    self.in_words = money_in_words(
                        self.grand_total, self.currency)
        else:
            if self.rounded_total:
                self.in_words = money_in_words(
                    self.rounded_total, self.currency)
            elif self.grand_total:
                self.in_words = money_in_words(self.grand_total, self.currency)

        # Always set base_in_words as before
        if self.base_rounded_total:
            self.base_in_words = money_in_words(
                self.base_rounded_total, self.company_currency)
        elif self.base_grand_total:
            self.base_in_words = money_in_words(
                self.base_grand_total, self.company_currency)

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
                item.purchase_invoice_item = matched.name

        # Force recalculation of totals
        self.calculate_taxes_and_totals()

    def fetch_invoice_data_for_items(self):
        """
        For each item in the Purchase Receipt, fetch matching data from the selected Purchase Invoice
        and update the item's fields. For UOM 'Unit', set base_amount = base_rate * qty, and set all price fields from invoice.
        Do NOT set received_stock_qty from invoice; always keep it from the receipt.
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
                # Set all price fields from invoice
                item.base_rate = matched.base_rate
                item.price_list_rate = getattr(matched, 'price_list_rate', 0)
                item.base_price_list_rate = getattr(
                    matched, 'base_price_list_rate', 0)
                if getattr(item, 'uom', None) == 'Unit':
                    item.base_amount = matched.base_rate * item.qty
                else:
                    item.base_amount = matched.base_amount
                item.stock_uom_rate = matched.stock_uom_rate
                item.net_rate = matched.net_rate
                item.net_amount = matched.net_amount
                item.base_net_rate = matched.base_net_rate
                item.base_net_amount = matched.base_net_amount
                item.purchase_invoice_item = matched.name
        # Do NOT set received_stock_qty from invoice. Only set if empty/zero elsewhere as fallback.

    def calculate_total_qty(self):
        """Mimic the frontend logic for total_qty calculation: if all UOMs are 'Unit', sum qty, else sum received_stock_qty."""
        all_unit = all(item.uom == "Unit" for item in self.items)
        if all_unit:
            return sum(flt(item.qty) for item in self.items)
        else:
            return sum(flt(item.received_stock_qty) for item in self.items)
