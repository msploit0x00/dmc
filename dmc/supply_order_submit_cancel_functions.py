# import frappe
# from frappe import _

# @frappe.whitelist()
# def restore_original_supply_order(original_order, current_order):
#     try:
#         # Get both documents
#         original_doc = frappe.get_doc("Supply order", original_order)
#         current_doc = frappe.get_doc("Supply order", current_order)

#         # Update quantities in the original supply order
#         for current_row in current_doc.custom_item_group_map:
#             for original_row in original_doc.custom_item_group_map:
#                 if original_row.item_group == current_row.item_group:
#                     # Calculate updated values
#                     updated_remainder = original_row.remainder + current_row.quantity
#                     updated_order_quantity = original_row.order_quantity - current_row.quantity

#                     # Update the original row
#                     frappe.db.set_value('Item Group Map', original_row.name, {
#                         'remainder': updated_remainder,
#                         'order_quantity': updated_order_quantity
#                     }, update_modified=True)

#         frappe.db.commit()
#         return True

#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), f"Error restoring original supply order quantities")
#         return False

# @frappe.whitelist()
# def process_supply_order_submit(original_order, current_order):
#     try:
#         # Get both documents
#         original_doc = frappe.get_doc("Supply order", original_order)
#         current_doc = frappe.get_doc("Supply order", current_order)

#         # First, reset all order_quantity values in current supply order to 0
#         for current_row in current_doc.custom_item_group_map:
#             frappe.db.set_value('Item Group Map', current_row.name, {
#                 'order_quantity': 0,
#                 'remainder': current_row.quantity  # Set remainder to full quantity
#             }, update_modified=True)

#         # Then update the original supply order's values
#         for current_row in current_doc.custom_item_group_map:
#             matching_row = None
            
#             # Find matching row in original supply order
#             for original_row in original_doc.custom_item_group_map:
#                 if original_row.item_group == current_row.item_group:
#                     matching_row = original_row
#                     break

#             if matching_row:
#                 # Calculate updated values
#                 updated_remainder = matching_row.remainder - current_row.quantity
#                 updated_order_quantity = (matching_row.order_quantity or 0) + current_row.quantity

#                 # Validate to ensure updated remainder doesn't fall below 0
#                 if updated_remainder < 0:
#                     frappe.throw(
#                         _('The remainder for item group "{0}" would fall below zero in the original Supply order.').format(
#                             current_row.item_group
#                         )
#                     )

#                 # Update the original row
#                 frappe.db.set_value('Item Group Map', matching_row.name, {
#                     'remainder': updated_remainder,
#                     'order_quantity': updated_order_quantity
#                 }, update_modified=True)
#             else:
#                 frappe.msgprint(
#                     _('Item group "{0}" not found in the original Supply order.').format(current_row.item_group),
#                     title=_('Missing Item Group'),
#                     indicator='orange'
#                 )

#         frappe.db.commit()
#         return True

#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), f"Error processing supply order submit")
#         return False

# @frappe.whitelist()
# def process_supply_order_cancel(original_order, current_order):
#     try:
#         # Get both documents
#         original_doc = frappe.get_doc("Supply order", original_order)
#         current_doc = frappe.get_doc("Supply order", current_order)

#         # Update quantities in the original supply order
#         for current_row in current_doc.custom_item_group_map:
#             matching_row = None
            
#             # Find matching row in original supply order
#             for original_row in original_doc.custom_item_group_map:
#                 if original_row.item_group == current_row.item_group:
#                     matching_row = original_row
#                     break

#             if matching_row:
#                 # Calculate updated values
#                 updated_remainder = matching_row.remainder + current_row.quantity
#                 updated_order_quantity = matching_row.order_quantity - current_row.quantity

#                 # Validate to ensure updated order_quantity doesn't fall below 0
#                 if updated_order_quantity < 0:
#                     frappe.throw(
#                         _('The order quantity for item group "{0}" would fall below zero in the original Supply order.').format(
#                             current_row.item_group
#                         )
#                     )

#                 # Update the original row
#                 frappe.db.set_value('Item Group Map', matching_row.name, {
#                     'remainder': updated_remainder,
#                     'order_quantity': updated_order_quantity
#                 }, update_modified=True)
#             else:
#                 frappe.msgprint(
#                     _('Item group "{0}" not found in the original Supply order.').format(current_row.item_group),
#                     title=_('Missing Item Group'),
#                     indicator='orange'
#                 )

#         frappe.db.commit()
#         return True

#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), f"Error processing supply order cancel")
#         return False 