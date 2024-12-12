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





#ahmed reda el king

@frappe.whitelist(allow_guest=True)
<<<<<<< HEAD
def set_remaining(rem, item_code, row_name):
=======
def set_remaining(rem,item_code,row_name):
>>>>>>> 5e33a24 (Ahmed Reda Task item code suuply order)
    
    update = frappe.db.sql("""

        UPDATE `tabQuotation Item`
<<<<<<< HEAD
        SET custom_remaining = %s,item_code = %s
        where name = %s 
=======
        SET custom_remaining = %s, item_code=%s
        where name = %s
>>>>>>> 5e33a24 (Ahmed Reda Task item code suuply order)
    
    
    
    
<<<<<<< HEAD
    """,(rem, item_code, row_name))
    frappe.db.commit()
=======
    """,(rem,item_code,row_name))
    frappe.db.commit()

>>>>>>> 5e33a24 (Ahmed Reda Task item code suuply order)
    print("UPDATE",update)
    return "Updated Successfully"






@frappe.whitelist(allow_guest=True)
def create_proforma(frm):
    try:
        data = json.loads(frm)

        # Extracting the required fields from the data
        prof = data.get("custom_proforma_invoice_details", [])
        invoice = data.get("payments", [])

        if not prof or not invoice:
            frappe.throw("Missing 'custom_proforma_invoice_details' or 'payments' in the request data.")

        # Iterating over each payment and associated proforma details
        for inv in invoice:
            reference_name = inv.get('reference_name')
            if not reference_name:
                frappe.throw("Missing 'reference_name' in payment entry.")

            for pr in prof:
                proforma_invoice = pr.get('proforma_invoice')
                grand_total = pr.get('grand_total')
                to_be_paid = pr.get('to_be_paid')

                if not all([proforma_invoice, grand_total, to_be_paid]):
                    frappe.throw(f"Missing required fields in proforma details: {pr}")

                # Creating the Proforma Invoice Details document
                doc = frappe.get_doc({
                    'doctype': 'Proforma Invoice Details',
                    'proforma_invoice': proforma_invoice,
                    'grand_total': grand_total,
                    'to_be_paid': to_be_paid,
                    'parenttype': 'Payment Entry',
                    'parent': reference_name,
                    'docstatus': 1,
                })

                # Inserting the document
                doc.insert(ignore_permissions=True)
                frappe.db.commit()

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Proforma Creation Error")
        frappe.throw(f"An error occurred: {str(e)}")

        # frappe.db.commit()



        # doctype: 'Quotation Item',
        #                 name: org.name ,
        #                 fieldname: 'custom_remaining',
        #                 # value: org.custom_remaining - org.custom_total_sub_qty
        
        
