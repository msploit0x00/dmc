import frappe
import json
from dmc.barcode_details import get_barcode_details

@frappe.whitelist()
def getConv_factor_for_uom(barcode, items, doc):
    if not barcode:
        return
    
    # Fetch barcode details
    data = get_barcode_details(barcode)
    print("=====================>",data)
    if not data:
        frappe.msgprint(f"Barcode {barcode} not found in barcode details.")
        return
    
    if "error" in data:
        frappe.msgprint(data["error"])
        return
        
    try:
        conversion_factor = data.get('conversion_factor')
        item_code = data.get('item_code')[0].get('parent') if data.get('item_code') else None
        batch_id = data.get('batch_id')
        
        if not all([conversion_factor, item_code, batch_id]):
            frappe.msgprint("Missing required barcode details")
            return
            
        return {
            "barcode": barcode,
            "item_code": item_code,
            "conversion_factor": conversion_factor,
            "batch_id": batch_id
        }
    except Exception as e:
        frappe.log_error(f"Error processing barcode {barcode}: {str(e)}")
        frappe.msgprint("Error processing barcode details")
        return None
  
