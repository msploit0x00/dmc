import frappe
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder



class CustomSalesOrder(SalesOrder):
    def on_update_after_submit(self):
       so_items = self.items
       supply_order = self.items[0].custom_supply_order

       sup_order_doc = frappe.get_doc("Supply order", supply_order)
       
       sup_items = sup_order_doc.items



       for row in so_items:
        for orginal in sup_items:
            if row.item_code == orginal.item_code:
                orginal.custom_remaining = orginal.qty - orginal.custom_total_sub_qty










        # doctype: 'Quotation Item',
        #                 name: org.name ,
        #                 fieldname: 'custom_remaining',
        #                 # value: org.custom_remaining - org.custom_total_sub_qty
        
        
