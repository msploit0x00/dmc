import frappe





@frappe.whitelist()
def get_projected_qty(item_code):
    tot_avail_qty = frappe.db.sql(
        "SELECT projected_qty FROM `tabBin` WHERE item_code = %s AND warehouse = 'All Warehouses - D'",
        (item_code,),  
        as_dict=False  
    )

    if tot_avail_qty:
        return tot_avail_qty[0][0]  # Return the first projected_qty value if it exists
    else:
        return 0  # Return 0 if no record is found

