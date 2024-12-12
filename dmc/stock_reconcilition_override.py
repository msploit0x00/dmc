import frappe
@frappe.whitelist()
def getConv_factor_for_uom(barcode:int):
  frappe.msgprint(f"barcode is {barcode}")
  sql = """



    """