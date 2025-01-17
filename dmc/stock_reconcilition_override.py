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
    
    conversion_factor = data.get('conversion_factor')[0].get('conversion_factor')
    item_code = data.get('item_code')[0].get('parent')
    batch_id = data.get('batch_id')
    return {"barcode":barcode,"item_code":item_code,"conversion_factor": conversion_factor,"batch_id":batch_id}
  