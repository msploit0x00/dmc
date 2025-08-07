from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
from frappe.utils import cint, flt
import frappe
from frappe import _


class CustomDeliveryNote(DeliveryNote):
    def validate_with_previous_doc(self):
        from erpnext.utilities.transaction_base import TransactionBase
        TransactionBase.validate_with_previous_doc(self, {
            "Sales Order": {
                "ref_dn_field": "against_sales_order",
                "compare_fields": [
                    ["customer", "="],
                    ["company", "="],
                    ["project", "="],
                    ["currency", "="],
                ],
            },
            "Sales Order Item": {
                "ref_dn_field": "so_detail",
                "compare_fields": [["item_code", "="]],
                "is_child_table": True,
                "allow_duplicate_prev_row_id": True,
            },
            "Sales Invoice": {
                "ref_dn_field": "against_sales_invoice",
                "compare_fields": [
                    ["customer", "="],
                    ["company", "="],
                    ["project", "="],
                    ["currency", "="],
                ],
            },
            "Sales Invoice Item": {
                "ref_dn_field": "si_detail",
                "compare_fields": [["item_code", "="]],
                "is_child_table": True,
                "allow_duplicate_prev_row_id": True,
            },
        })

        if cint(frappe.db.get_single_value("Selling Settings", "maintain_same_sales_rate")) and not self.is_return and not self.is_internal_customer:
            self.validate_rate_with_reference_doc([
                ["Sales Order", "against_sales_order", "so_detail"],
                ["Sales Invoice", "against_sales_invoice", "si_detail"],
            ])

    def validate(self):
        self.calculate_custom_amounts()
        self.calculate_custom_total_qty()
        super().validate()
        self.calculate_custom_amounts()
        self.calculate_custom_total_qty()

    def before_save(self):
        self.calculate_custom_amounts()
        self.calculate_custom_total_qty()

    def after_insert(self):
        self.calculate_custom_amounts()
        self.calculate_custom_total_qty()

    def on_update(self):
        self.calculate_custom_amounts()
        self.calculate_custom_total_qty()

    def before_submit(self):
        self.calculate_custom_amounts()
        self.calculate_custom_total_qty()

    def on_submit(self):
        super().on_submit()
        self.calculate_custom_amounts()
        self.calculate_custom_total_qty()

    def before_update_after_submit(self):
        self.calculate_custom_amounts()
        self.calculate_custom_total_qty()
        if hasattr(super(), 'before_update_after_submit'):
            super().before_update_after_submit()

    def calculate_custom_amounts(self):
        unit_uoms = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each']
        total_amount = 0
        conversion_rate = flt(self.conversion_rate) or 1.0

        for item in self.items:
            if item.get('is_free_item') or item.get('custom_is_free_item'):
                self._set_item_amounts(item, 0, conversion_rate)
                continue

            if not item.rate or not item.qty:
                continue

            conversion_factor = flt(item.conversion_factor) or 1.0
            if conversion_factor <= 0:
                conversion_factor = 1.0

            if not item.stock_qty:
                item.stock_qty = flt(item.qty) * conversion_factor

            uom_lower = (item.uom or '').lower().strip()
            is_unit_uom = uom_lower in unit_uoms

            if is_unit_uom:
                amount = flt(item.rate) * flt(item.qty)
            else:
                amount = flt(item.rate) * flt(item.stock_qty)

            self._set_item_amounts(item, amount, conversion_rate)
            total_amount += amount

        self._set_document_totals(total_amount, conversion_rate)

    def _set_item_amounts(self, item, amount, conversion_rate):
        base_amount = flt(amount) * flt(conversion_rate)
        item.amount = amount
        item.base_amount = base_amount
        item.net_amount = amount
        item.base_net_amount = base_amount

        if hasattr(item, 'price_list_rate') and not item.price_list_rate:
            item.price_list_rate = item.rate
        if hasattr(item, 'base_price_list_rate') and not item.base_price_list_rate:
            item.base_price_list_rate = item.rate * conversion_rate

    def _set_document_totals(self, total_amount, conversion_rate):
        base_total = flt(total_amount) * flt(conversion_rate)
        self.total = total_amount
        self.base_total = base_total
        self.net_total = total_amount
        self.base_net_total = base_total

    def calculate_custom_total_qty(self):
        unit_uoms = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each']
        unit_total = 0
        non_unit_total = 0

        for item in self.items:
            if not item.qty:
                continue

            uom_lower = (item.uom or '').lower().strip()
            is_unit_uom = uom_lower in unit_uoms

            if is_unit_uom:
                unit_total += flt(item.qty)
            else:
                stock_qty = flt(item.stock_qty) or (
                    flt(item.qty) * flt(item.conversion_factor or 1))
                non_unit_total += stock_qty

        self.total_qty = unit_total + non_unit_total

    def calculate_taxes_and_totals(self):
        self.calculate_custom_amounts()
        self.calculate_custom_total_qty()

        unit_uoms = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each']
        conversion_rate = flt(self.conversion_rate) or 1.0
        correct_taxable_amount = 0

        for item in self.items:
            if item.get('is_free_item') or item.get('custom_is_free_item'):
                continue

            if not item.rate or not item.qty:
                continue

            uom_lower = (item.uom or '').lower().strip()
            is_unit_uom = uom_lower in unit_uoms

            if is_unit_uom:
                item_taxable = flt(item.rate) * flt(item.qty)
            else:
                item_taxable = flt(item.rate) * flt(item.stock_qty or 0)

            correct_taxable_amount += item_taxable

        self.net_total = correct_taxable_amount
        self.total = correct_taxable_amount
        self.base_net_total = correct_taxable_amount * conversion_rate
        self.base_total = correct_taxable_amount * conversion_rate

        if self.taxes:
            cumulative_total = correct_taxable_amount
            for tax in self.taxes:
                if tax.charge_type == "On Net Total":
                    tax.tax_amount = flt(
                        correct_taxable_amount * flt(tax.rate) / 100)
                    tax.base_tax_amount = flt(tax.tax_amount * conversion_rate)
                    cumulative_total += tax.tax_amount
                    tax.total = cumulative_total
                    tax.base_total = flt(tax.total * conversion_rate)

            self.grand_total = cumulative_total
            self.base_grand_total = flt(cumulative_total * conversion_rate)
        else:
            self.grand_total = correct_taxable_amount
            self.base_grand_total = flt(
                correct_taxable_amount * conversion_rate)


# from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
# from frappe.utils import cint, flt
# import frappe
# from frappe import _


# class CustomDeliveryNote(DeliveryNote):
#     def validate_with_previous_doc(self):
#         """Override to allow flexible UOM and conversion factor changes between Sales Order and Delivery Note"""
#         # Call the parent class method from TransactionBase directly
#         from erpnext.utilities.transaction_base import TransactionBase
#         TransactionBase.validate_with_previous_doc(self, {
#             "Sales Order": {
#                 "ref_dn_field": "against_sales_order",
#                 "compare_fields": [
#                     ["customer", "="],
#                     ["company", "="],
#                     ["project", "="],
#                     ["currency", "="],
#                 ],
#             },
#             "Sales Order Item": {
#                 "ref_dn_field": "so_detail",
#                 # Removed UOM and conversion_factor validation
#                 "compare_fields": [["item_code", "="]],
#                 "is_child_table": True,
#                 "allow_duplicate_prev_row_id": True,
#             },
#             "Sales Invoice": {
#                 "ref_dn_field": "against_sales_invoice",
#                 "compare_fields": [
#                     ["customer", "="],
#                     ["company", "="],
#                     ["project", "="],
#                     ["currency", "="],
#                 ],
#             },
#             "Sales Invoice Item": {
#                 "ref_dn_field": "si_detail",
#                 # Removed UOM and conversion_factor validation
#                 "compare_fields": [["item_code", "="]],
#                 "is_child_table": True,
#                 "allow_duplicate_prev_row_id": True,
#             },
#         })

#         if (
#                 cint(frappe.db.get_single_value(
#                     "Selling Settings", "maintain_same_sales_rate"))
#                 and not self.is_return
#                 and not self.is_internal_customer
#         ):
#             self.validate_rate_with_reference_doc(
#                 [
#                     ["Sales Order", "against_sales_order", "so_detail"],
#                     ["Sales Invoice", "against_sales_invoice", "si_detail"],
#                 ]
#             )

#     def validate(self):
#         """Override validate to apply custom calculations multiple times"""
#         # Apply BEFORE parent validation
#         self.calculate_custom_amounts()
#         self.calculate_custom_total_qty()

#         # Call parent validate
#         super().validate()

#         # Apply AFTER parent validation (ERPNext might override)
#         self.calculate_custom_amounts()
#         self.calculate_custom_total_qty()

#     def before_save(self):
#         """Apply calculations right before saving"""
#         try:
#             self.calculate_custom_amounts()
#             self.calculate_custom_total_qty()
#             frappe.logger().info(
#                 f"✅ Custom calculations applied before save for DN: {self.name}")
#         except Exception as e:
#             frappe.logger().error(f"❌ Error in before_save: {str(e)}")

#     def after_insert(self):
#         """Apply calculations after document is inserted"""
#         try:
#             self.calculate_custom_amounts()
#             self.calculate_custom_total_qty()
#             frappe.logger().info(
#                 f"✅ Custom calculations applied after insert for DN: {self.name}")
#         except Exception as e:
#             frappe.logger().error(f"❌ Error in after_insert: {str(e)}")

#     def on_update(self):
#         """Apply calculations on every update"""
#         try:
#             self.calculate_custom_amounts()
#             self.calculate_custom_total_qty()
#             frappe.logger().info(
#                 f"✅ Custom calculations applied on update for DN: {self.name}")
#         except Exception as e:
#             frappe.logger().error(f"❌ Error in on_update: {str(e)}")

#     def before_submit(self):
#         """Apply calculations before submit"""
#         try:
#             self.calculate_custom_amounts()
#             self.calculate_custom_total_qty()
#             frappe.logger().info(
#                 f"✅ Custom calculations applied before submit for DN: {self.name}")
#         except Exception as e:
#             frappe.logger().error(f"❌ Error in before_submit: {str(e)}")

#     def on_submit(self):
#         """Apply calculations on submit"""
#         try:
#             # Call parent first
#             super().on_submit()

#             # Then apply our calculations
#             self.calculate_custom_amounts()
#             self.calculate_custom_total_qty()
#             frappe.logger().info(
#                 f"✅ Custom calculations applied on submit for DN: {self.name}")
#         except Exception as e:
#             frappe.logger().error(f"❌ Error in on_submit: {str(e)}")

#     def before_update_after_submit(self):
#         """Apply calculations before update after submit"""
#         try:
#             self.calculate_custom_amounts()
#             self.calculate_custom_total_qty()
#             frappe.logger().info(
#                 f"✅ Custom calculations applied before update after submit for DN: {self.name}")
#         except Exception as e:
#             frappe.logger().error(
#                 f"❌ Error in before_update_after_submit: {str(e)}")

#         if hasattr(super(), 'before_update_after_submit'):
#             super().before_update_after_submit()

#     def calculate_custom_amounts(self):
#         """Calculate amounts based on UOM type (Unit vs Box/Carton)"""
#         try:
#             if not self.items:
#                 return

#             unit_uoms = ['unit', 'units', 'nos',
#                          'pcs', 'piece', 'pieces', 'each']
#             total_amount = 0
#             conversion_rate = flt(self.conversion_rate) or 1.0

#             frappe.logger().info(
#                 f"🔧 Starting custom amount calculation for DN: {self.name}")

#             for item in self.items:
#                 try:
#                     # Handle free items
#                     if item.get('is_free_item') or item.get('custom_is_free_item'):
#                         self._set_item_amounts(item, 0, conversion_rate)
#                         frappe.logger().info(
#                             f"🎁 Free item {item.item_code}: amount set to 0")
#                         continue

#                     # Skip items without rate or qty
#                     if not item.rate or not item.qty:
#                         frappe.logger().warning(
#                             f"⚠️ Item {item.item_code}: missing rate ({item.rate}) or qty ({item.qty})")
#                         continue

#                     # Validate conversion factor
#                     conversion_factor = flt(item.conversion_factor) or 1.0
#                     if conversion_factor <= 0:
#                         conversion_factor = 1.0

#                     # Calculate stock_qty if missing
#                     if not item.stock_qty:
#                         item.stock_qty = flt(item.qty) * conversion_factor

#                     # Check UOM type for amount calculation
#                     uom_lower = (item.uom or '').lower().strip()
#                     is_unit_uom = uom_lower in unit_uoms

#                     # Calculate amount based on UOM for proper tax base
#                     if is_unit_uom:
#                         # Unit UOM: amount = rate × qty
#                         amount = flt(item.rate) * flt(item.qty)
#                         calc_type = "Unit UOM (rate × qty)"
#                         calc_details = f"{item.rate} × {item.qty}"
#                     else:
#                         # Box/Carton UOM: amount = rate × stock_qty
#                         amount = flt(item.rate) * flt(item.stock_qty)
#                         calc_type = "Box/Carton UOM (rate × stock_qty)"
#                         calc_details = f"{item.rate} × {item.stock_qty}"

#                     # Set the amount
#                     self._set_item_amounts(item, amount, conversion_rate)
#                     total_amount += amount

#                     frappe.logger().info(
#                         f"💰 Item {item.item_code}: {calc_type} = {calc_details} = {amount}")

#                 except Exception as item_error:
#                     frappe.logger().error(
#                         f"❌ Error calculating amount for item {item.item_code}: {str(item_error)}")
#                     continue

#             # Update document totals
#             self._set_document_totals(total_amount, conversion_rate)

#             frappe.logger().info(
#                 f"✅ Custom amounts calculated. Net Total: {self.net_total}")

#         except Exception as e:
#             frappe.logger().error(
#                 f"❌ Error in calculate_custom_amounts: {str(e)}")

#     def _set_item_amounts(self, item, amount, conversion_rate):
#         """Helper method to set all amount fields for an item"""
#         base_amount = flt(amount) * flt(conversion_rate)

#         # Set ALL possible amount fields
#         item.amount = amount
#         item.base_amount = base_amount
#         item.net_amount = amount
#         item.base_net_amount = base_amount

#         # For safety, also set price list rate fields if they exist
#         if hasattr(item, 'price_list_rate') and not item.price_list_rate:
#             item.price_list_rate = item.rate
#         if hasattr(item, 'base_price_list_rate') and not item.base_price_list_rate:
#             item.base_price_list_rate = item.rate * conversion_rate

#     def _set_document_totals(self, total_amount, conversion_rate):
#         """Helper method to set document total fields"""
#         base_total = flt(total_amount) * flt(conversion_rate)

#         # Set document totals
#         self.total = total_amount
#         self.base_total = base_total
#         self.net_total = total_amount
#         self.base_net_total = base_total

#         frappe.logger().info(
#             f"💰 Set document totals - Total: {self.total}, Net Total: {self.net_total}")

#     def calculate_custom_total_qty(self):
#         """Calculate total_qty as sum of qty for unit UOMs and stock_qty for non-unit UOMs"""
#         try:
#             unit_uoms = ['unit', 'units', 'nos',
#                          'pcs', 'piece', 'pieces', 'each']
#             unit_total = 0      # Sum of qty for Unit UOMs
#             non_unit_total = 0  # Sum of stock_qty for Non-Unit UOMs

#             for item in self.items:
#                 try:
#                     if not item.qty:
#                         continue

#                     uom_lower = (item.uom or '').lower().strip()
#                     is_unit_uom = uom_lower in unit_uoms

#                     if is_unit_uom:
#                         qty_to_add = flt(item.qty)
#                         unit_total += qty_to_add
#                         frappe.logger().info(
#                             f"📊 {item.item_code} (Unit UOM): qty={qty_to_add}")
#                     else:
#                         # For Box/Carton, use stock_qty
#                         qty_to_add = flt(item.stock_qty) or (
#                             flt(item.qty) * flt(item.conversion_factor or 1))
#                         non_unit_total += qty_to_add
#                         frappe.logger().info(
#                             f"📊 {item.item_code} (Box/Carton UOM): stock_qty={qty_to_add}")

#                 except Exception as item_error:
#                     frappe.logger().error(
#                         f"❌ Error calculating qty for item {item.item_code}: {str(item_error)}")
#                     continue

#             # NEW LOGIC: Always sum both unit and non-unit totals
#             self.total_qty = unit_total + non_unit_total
#             frappe.logger().info(
#                 f"📊 Final Total Qty: {self.total_qty} (Unit: {unit_total}, Non-Unit: {non_unit_total})")

#         except Exception as e:
#             frappe.logger().error(
#                 f"❌ Error in calculate_custom_total_qty: {str(e)}")

#     def calculate_taxes_and_totals(self):
#         """Override ERPNext's tax calculation with proper UOM handling"""
#         frappe.logger().info(
#             f"🔥 CUSTOM TAX CALCULATION for Delivery Note: {self.name}")

#         try:
#             # FIRST apply our custom calculations to get correct amounts
#             self.calculate_custom_amounts()
#             self.calculate_custom_total_qty()

#             unit_uoms = ['unit', 'units', 'nos',
#                          'pcs', 'piece', 'pieces', 'each']
#             conversion_rate = flt(self.conversion_rate) or 1.0

#             # Calculate correct taxable amount using UOM logic
#             correct_taxable_amount = 0

#             for item in self.items:
#                 if item.get('is_free_item') or item.get('custom_is_free_item'):
#                     continue

#                 if not item.rate or not item.qty:
#                     continue

#                 uom_lower = (item.uom or '').lower().strip()
#                 is_unit_uom = uom_lower in unit_uoms

#                 if is_unit_uom:
#                     # Unit UOM: taxable amount = rate × qty
#                     item_taxable = flt(item.rate) * flt(item.qty)
#                     frappe.logger().info(
#                         f"💰 {item.item_code} (Unit): {item.rate} × {item.qty} = {item_taxable}")
#                 else:
#                     # Box/Carton UOM: taxable amount = rate × stock_qty
#                     item_taxable = flt(item.rate) * flt(item.stock_qty or 0)
#                     frappe.logger().info(
#                         f"💰 {item.item_code} (Box): {item.rate} × {item.stock_qty} = {item_taxable}")

#                 correct_taxable_amount += item_taxable

#             frappe.logger().info(
#                 f"💰 Correct taxable amount: {correct_taxable_amount}")

#             # Update document totals with correct taxable amount
#             self.net_total = correct_taxable_amount
#             self.total = correct_taxable_amount
#             self.base_net_total = correct_taxable_amount * conversion_rate
#             self.base_total = correct_taxable_amount * conversion_rate

#             # Calculate taxes manually on correct taxable amount
#             if self.taxes:
#                 cumulative_total = correct_taxable_amount

#                 for tax in self.taxes:
#                     if tax.charge_type == "On Net Total":
#                         # Calculate tax on correct taxable amount
#                         tax.tax_amount = flt(
#                             correct_taxable_amount * flt(tax.rate) / 100)
#                         tax.base_tax_amount = flt(
#                             tax.tax_amount * conversion_rate)

#                         # Update cumulative total
#                         cumulative_total += tax.tax_amount
#                         tax.total = cumulative_total
#                         tax.base_total = flt(tax.total * conversion_rate)

#                         frappe.logger().info(
#                             f"💰 Tax: {tax.description} = {correct_taxable_amount} × {tax.rate}% = {tax.tax_amount}")

#                 # Update grand total
#                 self.grand_total = cumulative_total
#                 self.base_grand_total = flt(cumulative_total * conversion_rate)

#                 frappe.logger().info(f"💰 Grand Total: {self.grand_total}")
#             else:
#                 # No taxes - grand total equals net total
#                 self.grand_total = correct_taxable_amount
#                 self.base_grand_total = flt(
#                     correct_taxable_amount * conversion_rate)

#             frappe.logger().info(
#                 f"✅ Custom tax calculation complete for DN: {self.name}")

#         except Exception as e:
#             frappe.logger().error(
#                 f"❌ Error in custom tax calculation: {str(e)}")
#             # Fallback to parent method
#             super().calculate_taxes_and_totals()
