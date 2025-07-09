// frappe.ui.form.on('Delivery Note', {
//     validate: function (frm) {
//         const refMap = {};

//         // Build a map of item_code to ref qty (from Ref table)
//         frm.doc.custom_ref.forEach(ref => {
//             if (ref.item_code) {
//                 refMap[ref.item_code] = ref.quantity; // <-- Use correct field name here
//             }
//         });

//         const deliveryItemMap = {};

//         // Sum up quantities in Delivery Note Items
//         frm.doc.items.forEach(item => {
//             if (item.item_code) {
//                 deliveryItemMap[item.item_code] = (deliveryItemMap[item.item_code] || 0) + item.qty;
//             }
//         });

//         // Validate that each item in ref matches exactly in delivery items
//         for (const [item_code, ref_qty] of Object.entries(refMap)) {
//             const delivery_qty = deliveryItemMap[item_code] || 0;
//             if (delivery_qty !== ref_qty) {
//                 frappe.throw(
//                     `The total quantity for item ${item_code} must be exactly ${ref_qty}. Currently it is ${delivery_qty}.`
//                 );
//             }
//         }
//     }
// });
//         // For each row in Ref, sum matching items in Delivery Note Items
//         (frm.doc.custom_ref || []).forEach(ref => {
//             // Find all items that match this ref row
//             let matching_items = (frm.doc.items || []).filter(item =>
//                 item.item_code === ref.item_code &&
//                 (item.is_free_item || 0) === (ref.is_free_item || 0)
//                 // Add more fields here if needed, e.g. && item.batch_no === ref.batch_no
//             );
//             let total_qty = matching_items.reduce((sum, item) => sum + flt(item.qty), 0);

//             if (total_qty !== flt(ref.quantity)) {
//                 frappe.throw(
//                     `The total quantity for item ${ref.item_code} (Free: ${ref.is_free_item ? "Yes" : "No"}) must be exactly ${ref.quantity}. Currently it is ${total_qty}.`
//                 );
//             }
//         });
//     }
// });

// function sync_ref_table_with_items(frm) {
//     // Build a map of item_code to total qty in items table
//     let itemQtyMap = {};
//     (frm.doc.items || []).forEach(row => {
//         if (row.item_code) {
//             itemQtyMap[row.item_code] = (itemQtyMap[row.item_code] || 0) + flt(row.qty);
//         }
//     });

//     // Update the Ref table quantities to match the items table
//     (frm.doc.custom_ref || []).forEach(ref => {
//         if (ref.item_code && itemQtyMap[ref.item_code] !== undefined) {
//             frappe.model.set_value(ref.doctype, ref.name, 'quantity', itemQtyMap[ref.item_code]);
//         }
//     });
//     frm.refresh_field('custom_ref');
// }