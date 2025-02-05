import frappe

@frappe.whitelist()
def get_barcode_details(barcode):
    # Get the item code from the barcode
    item_code_data = frappe.get_all("Item Barcode", filters={'barcode': barcode}, fields=['parent'], limit=1)
    
    if not item_code_data:
        return {"error": "No Item Code for this barcode found"}
    
    item_code = item_code_data[0].get('parent')
    
    # Get the UOM from the barcode
    uom_data = frappe.get_all("Item Barcode", filters={'barcode': barcode}, fields=['uom'], limit=1)
    
    if not uom_data:
        return {"error": "No UOM for this barcode found"}
    
    uom = uom_data[0].get('uom')
    
    # Get the conversion factor for the item and UOM
    conversion_factor_data = frappe.get_all("UOM Conversion Detail", 
                                            filters={'parent': item_code, 'uom': uom}, 
                                            fields=['conversion_factor'], 
                                            limit=1)
    
    if not conversion_factor_data:
        return {"error": "No conversion factor found for this item and UOM"}
    
    conversion_factor = conversion_factor_data[0].get('conversion_factor')
    
    return {
        "item_code": item_code,
        "uom": uom,
        "conversion_factor": conversion_factor
    }
