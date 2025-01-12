import frappe




def clear_tax():
    items = frappe.get_all("Item",fields=['name'])


    for item in items:
        item_doc = frappe.get_doc("Item", item["name"])

        item_doc.taxes = []

        item_doc.save()

        frappe.db.commit()