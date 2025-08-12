from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note as erpnext_make_delivery_note
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

    # def validate(self):
    #     self.calculate_custom_amounts()
    #     self.calculate_custom_total_qty()
    #     super().validate()
    #     self.calculate_custom_amounts()
    #     self.calculate_custom_total_qty()

    def before_save(self):
        self.set_sales_order_links_on_items()
        self.ensure_free_items_zeroed()
        # self.calculate_custom_amounts()
        # self.calculate_custom_total_qty()

    def on_submit(self):
        super().on_submit()
        self.set_sales_order_links_on_items()
        self.ensure_free_items_zeroed()

    def before_update_after_submit(self):

        if hasattr(super(), 'before_update_after_submit'):
            super().before_update_after_submit()

    # def calculate_custom_amounts(self):
    #     unit_uoms = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each']
    #     total_amount = 0
    #     conversion_rate = flt(self.conversion_rate) or 1.0

    #     for item in self.items:
    #         if item.get('is_free_item') or item.get('custom_is_free_item'):
    #             self._set_item_amounts(item, 0, conversion_rate)
    #             continue

    #         if not item.rate or not item.qty:
    #             continue

    #         conversion_factor = flt(item.conversion_factor) or 1.0
    #         if conversion_factor <= 0:
    #             conversion_factor = 1.0

    #         if not item.stock_qty:
    #             item.stock_qty = flt(item.qty) * conversion_factor

    #         uom_lower = (item.uom or '').lower().strip()
    #         is_unit_uom = uom_lower in unit_uoms

    #         if is_unit_uom:
    #             amount = flt(item.rate) * flt(item.qty)
    #         else:
    #             amount = flt(item.rate) * flt(item.stock_qty)

    #         self._set_item_amounts(item, amount, conversion_rate)
    #         total_amount += amount

    #     self._set_document_totals(total_amount, conversion_rate)

    # def _set_item_amounts(self, item, amount, conversion_rate):
    #     base_amount = flt(amount) * flt(conversion_rate)
    #     item.amount = amount
    #     item.base_amount = base_amount
    #     item.net_amount = amount
    #     item.base_net_amount = base_amount

    #     if hasattr(item, 'price_list_rate') and not item.price_list_rate:
    #         item.price_list_rate = item.rate
    #     if hasattr(item, 'base_price_list_rate') and not item.base_price_list_rate:
    #         item.base_price_list_rate = item.rate * conversion_rate

    # def _set_document_totals(self, total_amount, conversion_rate):
    #     base_total = flt(total_amount) * flt(conversion_rate)
    #     self.total = total_amount
    #     self.base_total = base_total
    #     self.net_total = total_amount
    #     self.base_net_total = base_total

    # def calculate_custom_total_qty(self):
    #     unit_uoms = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each']
    #     unit_total = 0
    #     non_unit_total = 0

    #     for item in self.items:
    #         if not item.qty:
    #             continue

    #         uom_lower = (item.uom or '').lower().strip()
    #         is_unit_uom = uom_lower in unit_uoms

    #         if is_unit_uom:
    #             unit_total += flt(item.qty)
    #         else:
    #             stock_qty = flt(item.stock_qty) or (
    #                 flt(item.qty) * flt(item.conversion_factor or 1))
    #             non_unit_total += stock_qty

    #     self.total_qty = unit_total + non_unit_total

    # def calculate_taxes_and_totals(self):
    #     self.calculate_custom_amounts()
    #     self.calculate_custom_total_qty()

    #     unit_uoms = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each']
    #     conversion_rate = flt(self.conversion_rate) or 1.0
    #     correct_taxable_amount = 0

    #     for item in self.items:
    #         if item.get('is_free_item') or item.get('custom_is_free_item'):
    #             continue

    #         if not item.rate or not item.qty:
    #             continue

    #         uom_lower = (item.uom or '').lower().strip()
    #         is_unit_uom = uom_lower in unit_uoms

    #         if is_unit_uom:
    #             item_taxable = flt(item.rate) * flt(item.qty)
    #         else:
    #             item_taxable = flt(item.rate) * flt(item.stock_qty or 0)

    #         correct_taxable_amount += item_taxable

    #     self.net_total = correct_taxable_amount
    #     self.total = correct_taxable_amount
    #     self.base_net_total = correct_taxable_amount * conversion_rate
    #     self.base_total = correct_taxable_amount * conversion_rate

    #     if self.taxes:
    #         cumulative_total = correct_taxable_amount
    #         for tax in self.taxes:
    #             if tax.charge_type == "On Net Total":
    #                 tax.tax_amount = flt(
    #                     correct_taxable_amount * flt(tax.rate) / 100)
    #                 tax.base_tax_amount = flt(tax.tax_amount * conversion_rate)
    #                 cumulative_total += tax.tax_amount
    #                 tax.total = cumulative_total
    #                 tax.base_total = flt(tax.total * conversion_rate)

    #         self.grand_total = cumulative_total
    #         self.base_grand_total = flt(cumulative_total * conversion_rate)
    #     else:
    #         self.grand_total = correct_taxable_amount
    #         self.base_grand_total = flt(
    #             correct_taxable_amount * conversion_rate)


# --- PATCH: Ensure custom_is_free_item is copied from SO Item to DN Item ---

    def make_delivery_note_with_custom_fields(source_name, target_doc=None, kwargs=None):
        doc = erpnext_make_delivery_note(source_name, target_doc, kwargs)
        # Copy custom_is_free_item from SO Item to DN Item
        so = frappe.get_doc("Sales Order", source_name)
        so_items_map = {item.name: item for item in so.items}
        for dn_item in doc.items:
            so_item = so_items_map.get(dn_item.so_detail)
            if so_item and hasattr(dn_item, "custom_is_free_item"):
                dn_item.custom_is_free_item = so_item.custom_is_free_item
        return doc

    def set_sales_order_links_on_items(self):
        sales_order = getattr(self, "sales_order", None)
        if not sales_order:
            return
        try:
            so = frappe.get_doc("Sales Order", sales_order)
            so_items_map = {item.item_code: item for item in so.items}
            for item in self.items:
                if not item.against_sales_order:
                    item.against_sales_order = sales_order
                # Try to set so_detail if not set
                if not item.so_detail and item.item_code in so_items_map:
                    item.so_detail = so_items_map[item.item_code].name
        except Exception as e:
            frappe.logger().error(f"Error setting SO links on DN items: {e}")

    def ensure_free_items_zeroed(self):
        for item in self.items:
            if getattr(item, 'is_free_item', 0) or getattr(item, 'custom_is_free_item', 0):
                item.rate = 0
                item.amount = 0
