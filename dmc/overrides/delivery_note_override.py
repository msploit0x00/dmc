from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
from frappe.utils import cint, flt
import frappe
from frappe import _


class CustomDeliveryNote(DeliveryNote):
    def validate_with_previous_doc(self):
        """Override to allow flexible UOM and conversion factor changes between Sales Order and Delivery Note"""
        # Call the parent class method from TransactionBase directly
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
                # Removed UOM and conversion_factor validation
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
                # Removed UOM and conversion_factor validation
                "compare_fields": [["item_code", "="]],
                "is_child_table": True,
                "allow_duplicate_prev_row_id": True,
            },
        })

        if (
                cint(frappe.db.get_single_value(
                    "Selling Settings", "maintain_same_sales_rate"))
                and not self.is_return
                and not self.is_internal_customer
        ):
            self.validate_rate_with_reference_doc(
                [
                    ["Sales Order", "against_sales_order", "so_detail"],
                    ["Sales Invoice", "against_sales_invoice", "si_detail"],
                ]
            )

    def validate(self):
        """Override validate to apply custom calculations multiple times"""
        # Apply BEFORE parent validation
        self.calculate_custom_amounts()
        self.calculate_custom_total_qty()

        # Call parent validate
        super().validate()

        # Apply AFTER parent validation (ERPNext might override)
        self.calculate_custom_amounts()
        self.calculate_custom_total_qty()

        # Store our calculated values for later restoration
        self._store_custom_calculations()

    def before_save(self):
        """Apply calculations right before saving"""
        try:
            self.calculate_custom_amounts()
            self.calculate_custom_total_qty()
            frappe.logger().info(
                f"✅ Custom calculations applied before save for DN: {self.name}")
        except Exception as e:
            frappe.logger().error(f"❌ Error in before_save: {str(e)}")

    def after_insert(self):
        """Apply calculations after document is inserted"""
        try:
            self.calculate_custom_amounts()
            self.calculate_custom_total_qty()
            self._update_db_values()
            frappe.logger().info(
                f"✅ Custom calculations applied after insert for DN: {self.name}")
        except Exception as e:
            frappe.logger().error(f"❌ Error in after_insert: {str(e)}")

    def on_update(self):
        """Apply calculations on every update"""
        try:
            self.calculate_custom_amounts()
            self.calculate_custom_total_qty()
            self._update_db_values()
            frappe.logger().info(
                f"✅ Custom calculations applied on update for DN: {self.name}")
        except Exception as e:
            frappe.logger().error(f"❌ Error in on_update: {str(e)}")

    def before_submit(self):
        """Apply calculations before submit"""
        try:
            self.calculate_custom_amounts()
            self.calculate_custom_total_qty()
            self._update_db_values()
            frappe.logger().info(
                f"✅ Custom calculations applied before submit for DN: {self.name}")
        except Exception as e:
            frappe.logger().error(f"❌ Error in before_submit: {str(e)}")

    def on_submit(self):
        """Apply calculations on submit"""
        try:
            # Call parent first
            super().on_submit()

            # Then apply our calculations
            self.calculate_custom_amounts()
            self.calculate_custom_total_qty()
            self._update_db_values()
            frappe.logger().info(
                f"✅ Custom calculations applied on submit for DN: {self.name}")
        except Exception as e:
            frappe.logger().error(f"❌ Error in on_submit: {str(e)}")

    def before_update_after_submit(self):
        """Apply calculations before update after submit"""
        try:
            self.calculate_custom_amounts()
            self.calculate_custom_total_qty()
            frappe.logger().info(
                f"✅ Custom calculations applied before update after submit for DN: {self.name}")
        except Exception as e:
            frappe.logger().error(
                f"❌ Error in before_update_after_submit: {str(e)}")

        if hasattr(super(), 'before_update_after_submit'):
            super().before_update_after_submit()

    def _store_custom_calculations(self):
        """Store our custom calculations for restoration"""
        try:
            if not hasattr(self, '_custom_values'):
                self._custom_values = {}

            for item in self.items:
                self._custom_values[item.name] = {
                    'amount': item.amount,
                    'base_amount': item.base_amount,
                    'net_amount': item.net_amount,
                    'base_net_amount': item.base_net_amount
                }

            self._custom_values['document'] = {
                'total': self.total,
                'base_total': self.base_total,
                'net_total': self.net_total,
                'base_net_total': self.base_net_total,
                'total_qty': self.total_qty
            }

            frappe.logger().info(f"📦 Stored custom values for DN: {self.name}")
        except Exception as e:
            frappe.logger().error(f"❌ Error storing custom values: {str(e)}")

    def _update_db_values(self):
        """Force update values in database"""
        try:
            if not self.name or self.name.startswith('new-'):
                return

            # Update item amounts in database
            for item in self.items:
                if item.name and not item.name.startswith('new-'):
                    frappe.db.set_value('Delivery Note Item', item.name, {
                        'amount': item.amount,
                        'base_amount': item.base_amount,
                        'net_amount': item.net_amount,
                        'base_net_amount': item.base_net_amount
                    })

            # Update document totals in database
            frappe.db.set_value('Delivery Note', self.name, {
                'total': self.total,
                'base_total': self.base_total,
                'net_total': self.net_total,
                'base_net_total': self.base_net_total,
                'total_qty': self.total_qty
            })

            frappe.db.commit()
            frappe.logger().info(
                f"💾 Updated database values for DN: {self.name}")

        except Exception as e:
            frappe.logger().error(f"❌ Error updating database: {str(e)}")

    def calculate_custom_amounts(self):
        """Calculate amounts based on UOM type (Unit vs Box/Carton) and set in database"""
        try:
            if not self.items:
                return

            unit_uoms = ['unit', 'units', 'nos',
                         'pcs', 'piece', 'pieces', 'each']
            total_amount = 0
            conversion_rate = flt(self.conversion_rate) or 1.0

            frappe.logger().info(
                f"🔧 Starting custom amount calculation for DN: {self.name}")

            for item in self.items:
                try:
                    # Handle free items
                    if item.get('is_free_item') or item.get('custom_is_free_item'):
                        self._set_item_amounts(item, 0, conversion_rate)
                        frappe.logger().info(
                            f"🎁 Free item {item.item_code}: amount set to 0")
                        continue

                    # Skip items without rate or qty
                    if not item.rate or not item.qty:
                        frappe.logger().warning(
                            f"⚠️ Item {item.item_code}: missing rate ({item.rate}) or qty ({item.qty})")
                        continue

                    # Validate conversion factor
                    conversion_factor = flt(item.conversion_factor) or 1.0
                    if conversion_factor <= 0:
                        conversion_factor = 1.0

                    # Calculate stock_qty if missing
                    if not item.stock_qty:
                        item.stock_qty = flt(item.qty) * conversion_factor

                    # Check UOM type for amount calculation
                    uom_lower = (item.uom or '').lower().strip()
                    is_unit_uom = uom_lower in unit_uoms

                    # Calculate amount based on UOM for tax base
                    if is_unit_uom:
                        amount = flt(item.rate) * flt(item.qty)
                        calc_type = "Unit UOM (rate × qty)"
                        calc_details = f"{item.rate} × {item.qty}"
                    else:
                        amount = flt(item.rate) * flt(item.stock_qty)
                        calc_type = "Non-Unit UOM (rate × stock_qty)"
                        calc_details = f"{item.rate} × {item.stock_qty}"

                    # FORCE set the amount - this is our calculated value
                    self._set_item_amounts(item, amount, conversion_rate)
                    total_amount += amount

                    frappe.logger().info(
                        f"💰 Item {item.item_code}: {calc_type} = {calc_details} = {amount}")

                except Exception as item_error:
                    frappe.logger().error(
                        f"❌ Error calculating amount for item {item.item_code}: {str(item_error)}")
                    continue

            # Update document totals
            self._set_document_totals(total_amount, conversion_rate)

            frappe.logger().info(
                f"✅ Custom amounts calculated. Net Total: {self.net_total}")

        except Exception as e:
            frappe.logger().error(
                f"❌ Error in calculate_custom_amounts: {str(e)}")

    def _set_item_amounts(self, item, amount, conversion_rate):
        """Helper method to set all amount fields for an item - AGGRESSIVELY"""
        base_amount = flt(amount) * flt(conversion_rate)

        # Set ALL possible amount fields
        item.amount = amount
        item.base_amount = base_amount
        item.net_amount = amount
        item.base_net_amount = base_amount

        # For safety, also set price list rate fields if they exist
        if hasattr(item, 'price_list_rate') and not item.price_list_rate:
            item.price_list_rate = item.rate
        if hasattr(item, 'base_price_list_rate') and not item.base_price_list_rate:
            item.base_price_list_rate = item.rate * conversion_rate

    def _set_document_totals(self, total_amount, conversion_rate):
        """Helper method to set document total fields"""
        base_total = flt(total_amount) * flt(conversion_rate)

        # FORCE total to equal net_total (both should be the sum of item amounts)
        self.total = total_amount
        self.base_total = base_total
        self.net_total = total_amount
        self.base_net_total = base_total

        frappe.logger().info(
            f"💰 Set document totals - Total: {self.total}, Net Total: {self.net_total}")

    def calculate_custom_total_qty(self):
        """Calculate total_qty based on UOM (qty for Unit, stock_qty for Box/Carton)"""
        try:
            unit_uoms = ['unit', 'units', 'nos',
                         'pcs', 'piece', 'pieces', 'each']
            total_qty = 0

            for item in self.items:
                try:
                    if not item.qty:
                        continue

                    uom_lower = (item.uom or '').lower().strip()

                    if uom_lower in unit_uoms:
                        qty_to_add = flt(item.qty)
                    else:
                        qty_to_add = flt(item.stock_qty) or (
                            flt(item.qty) * flt(item.conversion_factor or 1))

                    total_qty += qty_to_add

                except Exception as item_error:
                    frappe.logger().error(
                        f"❌ Error calculating qty for item {item.item_code}: {str(item_error)}")
                    continue

            self.total_qty = total_qty
            frappe.logger().info(f"📊 Total Qty calculated: {total_qty}")

        except Exception as e:
            frappe.logger().error(
                f"❌ Error in calculate_custom_total_qty: {str(e)}")

    # TEMPORARILY DISABLED to avoid conflicts with JavaScript implementation
    def calculate_taxes_and_totals_DISABLED(self):
        """Override ERPNext's tax calculation to use our correct amounts"""
        print(f"🔥 PYTHON OVERRIDE CALLED for Delivery Note: {self.name}")
        frappe.logger().info(
            f"🔥 PYTHON OVERRIDE CALLED for Delivery Note: {self.name}")
        try:
            # FIRST apply our custom calculations to get correct amounts
            self.calculate_custom_amounts()
            self.calculate_custom_total_qty()

            frappe.logger().info(
                f"🔄 Starting tax calculation with net_total: {self.net_total}")
            print(
                f"🔄 Starting tax calculation with net_total: {self.net_total}")

            # Store our correct values
            our_net_total = flt(self.net_total)
            our_total = flt(self.total)
            our_total_qty = flt(self.total_qty)
            conversion_rate = flt(self.conversion_rate) or 1.0

            print(f"💰 Our correct net_total: {our_net_total}")
            print(
                f"📋 Number of tax rows: {len(self.taxes) if self.taxes else 0}")

            # Calculate taxes manually on OUR correct net_total
            if self.taxes:
                cumulative_total = our_net_total

                for tax in self.taxes:
                    if tax.charge_type == "On Net Total":
                        # Calculate tax on OUR net_total (not ERPNext's wrong total)
                        old_tax_amount = tax.tax_amount
                        tax.tax_amount = flt(
                            our_net_total * flt(tax.rate) / 100)
                        tax.base_tax_amount = flt(
                            tax.tax_amount * conversion_rate)

                        # Update cumulative total
                        cumulative_total += tax.tax_amount
                        tax.total = cumulative_total
                        tax.base_total = flt(tax.total * conversion_rate)

                        print(
                            f"💰 Tax calculated: {tax.description} = {our_net_total} × {tax.rate}% = {tax.tax_amount} (was: {old_tax_amount})")
                        frappe.logger().info(
                            f"💰 Tax calculated: {tax.description} = {our_net_total} × {tax.rate}% = {tax.tax_amount}")

                # Update document grand total
                self.grand_total = cumulative_total
                self.base_grand_total = flt(cumulative_total * conversion_rate)

                print(
                    f"💰 Final totals - Net: {our_net_total}, Tax: {cumulative_total - our_net_total}, Grand: {self.grand_total}")
                frappe.logger().info(
                    f"💰 Final totals - Net: {our_net_total}, Tax: {cumulative_total - our_net_total}, Grand: {self.grand_total}")
            else:
                print("❌ No taxes found!")
                # No taxes - grand total equals net total
                self.grand_total = our_net_total
                self.base_grand_total = flt(our_net_total * conversion_rate)

            # FORCE set all totals to our calculated values
            self.net_total = our_net_total
            self.total = our_total
            self.base_net_total = flt(our_net_total * conversion_rate)
            self.base_total = flt(our_total * conversion_rate)
            self.total_qty = our_total_qty

            frappe.logger().info(
                f"✅ Tax calculation complete for DN: {self.name}")

        except Exception as e:
            frappe.logger().error(
                f"❌ Error in calculate_taxes_and_totals override: {str(e)}")
            # Fallback: Apply our amounts then call parent
            self.calculate_custom_amounts()
            self.calculate_custom_total_qty()
            super().calculate_taxes_and_totals()
