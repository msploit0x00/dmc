import frappe





@frappe.whitelist(allow_guest=True)
def get_item_code(barcode):
    
    data = frappe.get_all("Item Barcode", filters={'barcode': barcode},fields=['parent'])

    if len(data) > 0:
        return data
    
    else:
        return "No Item Code for this barcode found"
    