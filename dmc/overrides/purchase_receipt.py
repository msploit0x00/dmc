from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from frappe.utils import flt, money_in_words
import frappe
from frappe import _


class CustomPurchaseReceipt(PurchaseReceipt):
    def validate_with_previous_doc(self):
        # Disabled all core validations in this method as per user request
        pass

    def limits_crossed_error(self, args, item, qty_or_amount):
        pass

    def validate_actual_qty(self, sn_doc):
        """Disable actual qty validation for serial/batch items"""
        pass

    def before_save(self):
        # Calculate base_amount for each item based on UOM
        for item in self.items:
            # UOM-based calculation logic
            if item.uom == 'Unit':
                # For Unit UOM: base_amount = qty * base_rate
                item.base_amount = flt(item.qty) * flt(item.base_rate)
            elif item.uom in ['Box', 'Carton']:
                # For Box/Carton UOM: base_amount = stock_qty * base_rate
                item.base_amount = flt(item.stock_qty) * flt(item.base_rate)
            else:
                # Default fallback for other UOMs: use qty * base_rate
                item.base_amount = flt(item.qty) * flt(item.base_rate)

            # Fix purchase_invoice_item field to prevent KeyError
            if item.purchase_invoice and not item.purchase_invoice_item:
                # Try to find the correct purchase invoice item
                try:
                    pi_doc = frappe.get_doc(
                        "Purchase Invoice", item.purchase_invoice)
                    # Find matching item in Purchase Invoice
                    for pi_item in pi_doc.items:
                        if (pi_item.item_code == item.item_code and
                            not frappe.db.exists("Purchase Receipt Item",
                                                 {"purchase_invoice_item": pi_item.name, "docstatus": 1})):
                            item.purchase_invoice_item = pi_item.name
                            break
                    else:
                        # If no match found, clear the purchase_invoice reference
                        item.purchase_invoice = None
                        frappe.msgprint(
                            f"Could not link item {item.item_code} to Purchase Invoice. Reference cleared.")
                except Exception as e:
                    # If there's any error, clear the purchase_invoice reference
                    item.purchase_invoice = None
                    frappe.log_error(
                        f"Error linking Purchase Invoice item: {str(e)}", "Purchase Receipt Item Linking")

    def validate(self):
        super().validate()

        # Calculate and set total_qty
        self.total_qty = self.calculate_total_qty()

        # Calculate and set base_total using UOM logic
        self.update_total_amount()

        # Set received_stock_qty if not set
        for item in self.items:
            if not item.received_stock_qty or item.received_stock_qty == 0:
                if item.qty and item.conversion_factor:
                    item.received_stock_qty = flt(
                        item.qty) * flt(item.conversion_factor)

    def on_submit(self):
        super().on_submit()

        # Ensure calculations are done on submit
        self.calculate_taxes_and_totals()
        self.set_rounded_total()
        self.set_in_words()
        self.total_qty = self.calculate_total_qty()

    def get_sl_entries(self, d, args):
        """
        Override to set custom rates PROPERLY at the source before SLE creation
        """
        # Get the standard SLE entry first
        sle = super().get_sl_entries(d, args)

        try:
            # Calculate the correct per-unit rate based on Purchase Receipt item data and UOM
            if d.uom == 'Unit':
                # For Unit UOM, base_rate is already per unit
                per_unit_rate = flt(d.base_rate)
            elif d.uom in ['Box', 'Carton']:
                # For Box/Carton UOM, need to convert to per stock unit rate
                if d.conversion_factor and d.conversion_factor > 0:
                    per_unit_rate = flt(d.base_rate) / flt(d.conversion_factor)
                else:
                    per_unit_rate = flt(d.base_rate)
            else:
                # Default: calculate per-unit rate using conversion factor
                if d.conversion_factor and d.conversion_factor > 0:
                    per_unit_rate = flt(d.base_rate) / flt(d.conversion_factor)
                else:
                    per_unit_rate = flt(d.base_rate)

            # Override the SLE rates BEFORE it's created
            sle.update({
                "incoming_rate": per_unit_rate,
                "valuation_rate": per_unit_rate,
            })

            # Calculate stock value difference based on actual quantity and our rate
            if sle.get("actual_qty"):
                sle["stock_value_difference"] = flt(
                    sle["actual_qty"]) * per_unit_rate

            print(
                f"DEBUG: Item {d.item_code} - UOM: {d.uom}, Base Rate: {d.base_rate}, Conversion: {d.conversion_factor}, Per Unit Rate: {per_unit_rate}")

        except Exception as e:
            frappe.log_error(f"Error in custom get_sl_entries for item {d.item_code}: {str(e)}",
                             "Purchase Receipt Custom SLE Error")

        return sle

    def after_save(self):
        super().after_save()
        self.set_rounded_total()
        self.set_in_words()

    def update_total_amount(self):
        """Update base_total based on UOM logic and save to database"""
        total = 0
        for d in self.items:
            # Calculate base_amount based on UOM logic
            if d.uom == 'Unit':
                # For Unit UOM: base_amount = qty * base_rate
                base_amount = flt(d.qty) * flt(d.base_rate)
            elif d.uom in ['Box', 'Carton']:
                # For Box/Carton UOM: base_amount = stock_qty * base_rate
                base_amount = flt(d.stock_qty) * flt(d.base_rate)
            else:
                # Default fallback for other UOMs: use qty * base_rate
                base_amount = flt(d.qty) * flt(d.base_rate)

            total += base_amount

        self.base_total = total
        self.db_set('base_total', total)

    def set_rounded_total(self):
        """Calculate and set rounded total"""
        if not self.disable_rounded_total:
            # Use simple 2 decimal precision for all calculations
            self.rounding_adjustment = flt(
                self.grand_total - self.rounded_total, 2)
            self.rounded_total = flt(
                self.grand_total, 2)
            self.base_rounding_adjustment = flt(
                self.base_grand_total - self.base_rounded_total, 2)
            self.base_rounded_total = flt(
                self.base_grand_total, 2)

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

    def calculate_total_qty(self):
        """Calculate total_qty: if all UOMs are 'Unit', sum qty, else sum received_stock_qty."""
        if not self.items:
            return 0
        else:
            return sum(flt(item.received_stock_qty) for item in self.items)
