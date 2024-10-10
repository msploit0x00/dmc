import frappe
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder


class CustomSalesOrder(SalesOrder):
    def on_update_after_submit(self):
        so_items = self.items
        supply_order = self.items[0].custom_supply_order

        sup_order_doc = frappe.get_doc("Supply order", supply_order)  # Ensure correct casing

        sup_items = sup_order_doc.items

        for row in so_items:
            for original in sup_items:
                if row.item_code == original.item_code:
                    original.custom_remaining = original.qty - original.custom_total_sub_qty

        sup_order_doc.save()  # Save the changes
        frappe.db.commit()  # Commit the changes to the database








        # doctype: 'Quotation Item',
        #                 name: org.name ,
        #                 fieldname: 'custom_remaining',
        #                 # value: org.custom_remaining - org.custom_total_sub_qty
        
        
