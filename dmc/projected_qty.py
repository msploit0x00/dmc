import frappe





@frappe.whitelist()
def get_projected_qty(item_code):
    tot_avail_qty = frappe.db.sql(
        "SELECT SUM(projected_qty) FROM `tabBin` WHERE item_code = %s",
        (item_code,),  
        as_dict=False
    )

    if tot_avail_qty and tot_avail_qty[0][0] is not None:
        return tot_avail_qty[0][0]  
    else:
        return 0  


