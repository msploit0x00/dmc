import frappe





@frappe.whitelist(allow_guest=True)
def get_item_code(barcode):
    
    data = frappe.get_all("Item Barcode", filters={'barcode': barcode},fields=['parent'])

    if len(data) > 0:
        return data
    
    else:
        return "No Item Code for this barcode found"




@frappe.whitelist(allow_guest=True)
def get_barcode_uom(barcode):
    
    data = frappe.get_all("Item Barcode", filters={'barcode': barcode},fields=['uom'],limit=1)

    if len(data) > 0:
        return data
    
    else:
        return "No Item Code for this barcode found"




@frappe.whitelist(allow_guest=True)
def get_conversion_factor(item_code,uom):

    data = frappe.get_all("UOM Conversion Detail", 
    filters={'parent': item_code,'uom': uom},
    fields=['conversion_factor'],
    limit=1)

    if len(data) > 0:
        return data
    else:
        return "no data found"


    