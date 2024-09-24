import frappe






@frappe.whitelist()
def get_projected_qty(item_code):

    tot_avail_qty = frappe.db.sql(
				"select projected_qty from `tabBin` \
				where item_code = %s and warehouse = 'All Warehouses - D'",
				(item_code),
			)

    return tot_avail_qty
