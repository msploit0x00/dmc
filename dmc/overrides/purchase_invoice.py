from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice
import frappe
from frappe.utils import flt

class CustomPurchaseInvoice(PurchaseInvoice):
    def calculate_taxes_and_totals(self):
        """Calculate net total after applying shipping for Metrex supplier"""
        
        # Let parent calculate amounts normally first
        super().calculate_taxes_and_totals()
        
        # Apply shipping multiplier for Metrex
        if self.supplier == "Metrex":
            shipping_applied = False
            
            for item in self.items:
                shipping = flt(item.custom_shipping) or 1
                if shipping != 1:
                    shipping_applied = True
                    # Multiply amounts by shipping (rate and qty stay unchanged)
                    item.amount = flt(item.amount * shipping, item.precision("amount"))
                    item.net_amount = flt(item.net_amount * shipping, item.precision("net_amount"))
                    item.base_amount = flt(item.base_amount * shipping, item.precision("base_amount"))
                    item.base_net_amount = flt(item.base_net_amount * shipping, item.precision("base_net_amount"))
            
            if shipping_applied:
                # Recalculate net totals
                self.net_total = sum([flt(item.net_amount) for item in self.items])
                self.base_net_total = sum([flt(item.base_net_amount) for item in self.items])
                self.total = self.net_total
                self.base_total = self.base_net_total
                
                # Recalculate taxes based on new net_total
                self._recalculate_taxes()
                
                # Recalculate grand total
                self._recalculate_grand_total()
    
    def _recalculate_taxes(self):
        """Recalculate all taxes based on updated totals"""
        cumulative_tax = 0
        base_cumulative_tax = 0
        
        for i, tax in enumerate(self.get("taxes")):
            # Calculate tax amount based on charge type
            if tax.charge_type == "Actual":
                # Actual amount doesn't change
                actual_tax_amount = flt(tax.tax_amount, tax.precision("tax_amount"))
                actual_base_tax_amount = flt(tax.base_tax_amount, tax.precision("base_tax_amount"))
            
            elif tax.charge_type == "On Net Total":
                actual_tax_amount = flt((self.net_total * flt(tax.rate)) / 100, tax.precision("tax_amount"))
                actual_base_tax_amount = flt((self.base_net_total * flt(tax.rate)) / 100, tax.precision("base_tax_amount"))
            
            elif tax.charge_type == "On Previous Row Amount":
                if i > 0:
                    previous_tax = self.get("taxes")[i-1]
                    actual_base_tax_amount = flt((flt(previous_tax.base_tax_amount) * flt(tax.rate)) / 100, tax.precision("base_tax_amount"))
                    actual_tax_amount = flt((flt(previous_tax.tax_amount) * flt(tax.rate)) / 100, tax.precision("tax_amount"))
                else:
                    actual_tax_amount = 0
                    actual_base_tax_amount = 0
            
            elif tax.charge_type == "On Previous Row Total":
                if i > 0:
                    previous_tax = self.get("taxes")[i-1]
                    actual_base_tax_amount = flt((flt(previous_tax.base_total) * flt(tax.rate)) / 100, tax.precision("base_tax_amount"))
                    actual_tax_amount = flt((flt(previous_tax.total) * flt(tax.rate)) / 100, tax.precision("tax_amount"))
                else:
                    actual_base_tax_amount = flt((self.base_net_total * flt(tax.rate)) / 100, tax.precision("base_tax_amount"))
                    actual_tax_amount = flt((self.net_total * flt(tax.rate)) / 100, tax.precision("tax_amount"))
            
            else:
                actual_tax_amount = flt(tax.tax_amount, tax.precision("tax_amount"))
                actual_base_tax_amount = flt(tax.base_tax_amount, tax.precision("base_tax_amount"))
            
            # Update tax amounts
            tax.tax_amount = actual_tax_amount
            tax.base_tax_amount = actual_base_tax_amount
            
            # Calculate after discount amounts (if discount exists)
            if hasattr(tax, 'tax_amount_after_discount_amount'):
                tax.tax_amount_after_discount_amount = actual_tax_amount
                tax.base_tax_amount_after_discount_amount = actual_base_tax_amount
            
            # Update cumulative totals based on add/deduct
            if tax.add_deduct_tax == "Add":
                cumulative_tax += actual_tax_amount
                base_cumulative_tax += actual_base_tax_amount
            else:
                cumulative_tax -= actual_tax_amount
                base_cumulative_tax -= actual_base_tax_amount
            
            # Set running total
            tax.total = flt(self.net_total + cumulative_tax, tax.precision("total"))
            tax.base_total = flt(self.base_net_total + base_cumulative_tax, tax.precision("base_total"))
    
    def _recalculate_grand_total(self):
        """Recalculate grand total after tax updates"""
        # Start with net total
        self.grand_total = flt(self.net_total, self.precision("grand_total"))
        self.base_grand_total = flt(self.base_net_total, self.precision("base_grand_total"))
        
        # Add/subtract taxes
        self.total_taxes_and_charges = 0
        self.base_total_taxes_and_charges = 0
        
        for tax in self.get("taxes"):
            if tax.add_deduct_tax == "Add":
                self.grand_total += flt(tax.tax_amount)
                self.base_grand_total += flt(tax.base_tax_amount)
                self.total_taxes_and_charges += flt(tax.tax_amount)
                self.base_total_taxes_and_charges += flt(tax.base_tax_amount)
            else:
                self.grand_total -= flt(tax.tax_amount)
                self.base_grand_total -= flt(tax.base_tax_amount)
                self.total_taxes_and_charges -= flt(tax.tax_amount)
                self.base_total_taxes_and_charges -= flt(tax.base_tax_amount)
        
        # Round the values
        self.grand_total = flt(self.grand_total, self.precision("grand_total"))
        self.base_grand_total = flt(self.base_grand_total, self.precision("base_grand_total"))
        
        # Set rounded total
        self._set_rounded_total()
        
        # Calculate outstanding amount
        self.outstanding_amount = flt(
            self.rounded_total or self.grand_total,
            self.precision("outstanding_amount")
        )
    
    def _set_rounded_total(self):
        """Set rounded total if not disabled"""
        if self.get("disable_rounded_total"):
            self.rounded_total = 0
            self.base_rounded_total = 0
            self.rounding_adjustment = 0
            self.base_rounding_adjustment = 0
        else:
            from frappe.utils import rounded
            self.rounded_total = rounded(self.grand_total)
            self.base_rounded_total = rounded(self.base_grand_total)
            
            if self.rounded_total:
                self.rounding_adjustment = flt(
                    self.rounded_total - self.grand_total, 
                    self.precision("rounding_adjustment")
                )
                self.base_rounding_adjustment = flt(
                    self.base_rounded_total - self.base_grand_total,
                    self.precision("base_rounding_adjustment")
                )