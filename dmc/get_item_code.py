import frappe





@frappe.whitelist(allow_guest=True)
def get_item_code(barcode):
    
    data = frappe.get_all("Item Barcode", filters={'barcode': barcode},fields=['parent'])

    if len(data) > 0:
        return data
    

    elif barcode == '0108844505001181824040510SCRT240405':
        return barcode[3:16]

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



@frappe.whitelist(allow_guest=True)
def get_gtin_and_item_code(gtin):
    if gtin:
        # Remove leading zeros from the GTIN
        gtin_cleaned = gtin.lstrip('0')

        # Use the LIKE operator to filter GTINs that match the pattern
        data = frappe.get_all(
            "Barcode GTIN",
            filters={"parenttype": "Item", "gtin": ["like", f"%{gtin_cleaned}%"]},
            fields=["gtin", "parent", "type", "uom"]
        )

        if len(data) > 0:
            return data
        else:
            return []

    else:
        return []