import frappe
import json
# from erpnext.selling.doctype.sales_order.sales_order import SalesOrder


# class CustomSalesOrder(SalesOrder):
#     def on_submit(self):
#         so_items = self.items
#         supply_order = self.items[0].custom_supply_order

#         sup_order_doc = frappe.get_doc("Supply order", supply_order)  

#         sup_items = sup_order_doc.items

#         for row in so_items:
#             for original in sup_items:
#                 if row.item_code == original.item_code:
#                     original.custom_remaining = original.qty - original.custom_total_sub_qty







@frappe.whitelist(allow_guest=True)
def set_remaining(rem,row_name):
    
    update = frappe.db.sql("""

        UPDATE `tabQuotation Item`
        SET custom_remaining = %s
        where name = %s
    
    
    
    
    """,(rem,row_name))
    frappe.db.commit()

    return "Updated Successfully"







def create_proforma(frm):

    data =json.loads(frm)

    prof = data.get("custom_proforma_invoice_details")

    invoice = data.get("invoices")

    for inv in invoice:
        for pr in prof:
            doc = frappe.new_doc("Proforma Invoice Details",{
        'proforma_invoice': pr["proforma_invoice"],
        'grand_total': pr["grand_total"],
        'to_be_paid': pr["to_be_paid"],
        'parenttype': 'Payment Entry',
        'parent': inv['invoice_number'],
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()



        # doctype: 'Quotation Item',
        #                 name: org.name ,
        #                 fieldname: 'custom_remaining',
        #                 # value: org.custom_remaining - org.custom_total_sub_qty
        
        
