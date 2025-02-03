
// frappe.ui.form.on("Stock Reconciliation", {
//   custom_barcode(frm) {
//     frappe.call({
//       method: "dmc.stock_reconcilition_override.getConv_factor_for_uom",
//       args: {
//         barcode: frm.doc.custom_barcode,
//         items: frm.doc.items,
//         doc: frm.doc,
//       },
//       callback: function (res) {
//         console.log("response", res.message);

//         // Check if response contains the necessary fields
//         if (res.message) {
//           var items = frm.doc.items;
//           for (let item of items) {
//             if (item.item_code === res.message.item_code) {
//               // If the item exists, update or add child row as needed
//               let child = frm.add_child('items');
//               // let child = frappe.model.add_child("Stock Reconciliation Item",'items');
//               child.item_code = res.message.item_code;  // Set item_code
//               child.conversion_factor = res.message.conversion_factor; // Set conversion_factor
//               frm.refresh_field("items");
//             } else {
//               // For other items, add a new row with default values
//               let child = frm.add_child('items');
//               child.item_code = item.item_code;  // Use the existing item_code from items
//               child.conversion_factor = 1; // Or any default value if needed
//               frm.refresh_field("items");
//             }
//           }
          
//         } else {
//           frappe.msgprint("Invalid response from the server.");
//         }
        
//       },
//     });
//   },
// });












/////////////////////////Running//////////////////////////////





// frappe.ui.form.on("Stock Reconciliation", {
//   custom_barcode(frm) {
//     // Guard against infinite loop by checking if the event has already been processed
//     if (frm.custom_barcode_processed) {
//       return; // If the flag is set, exit the function
//     }

//     frm.custom_barcode_processed = true; // Set the flag to true to indicate processing

//     frappe.call({
//       method: "dmc.stock_reconcilition_override.getConv_factor_for_uom",
//       args: {
//         barcode: frm.doc.custom_barcode,
//         items: frm.doc.items,
//         doc: frm.doc,
//       },
//       callback: function (res) {
//         console.log("response", res.message);

//         // Reset the flag after the processing is done
//         frm.custom_barcode_processed = false;

//         // Check if response contains the necessary fields
//         if (res.message) {
//           let existing_item_codes = frm.doc.items.map(item => item.item_code);
//           let item_added = false;
//           console.log("res.message.barcode", res.message.barcode);
//           console.log("res.message.item_code", res.message.item_code);
//           console.log("res.message.conversion_factor", res.message.conversion_factor);
//           console.log("res.message.batch_no", res.message.batch_no);
//           // Loop through existing items to check if item exists
//           for (let item of frm.doc.items) {
//             if (item.item_code === res.message.item_code) {
//               // If the item exists, increment the quantity by the conversion factor
//               item.qty += res.message.conversion_factor;
//               item_added = true;
//               break; // No need to add a new row, just update the existing one
//             }
//           }

//           // If the item was not found in the existing items, add a new row
//           if (!item_added) {
//             let child = frm.add_child('items',{
//               "barcode":res.message.barcode,
//               "item_code":res.message.item_code,
//               "qty":res.message.conversion_factor,
//               "use_serial_batch_fields":1,  
//               "batch_no":res.message.batch_id,
//             });
//             // child.item_code = res.message.item_code;  // Set item_code
//             // child.qty = res.message.conversion_factor; // Set qty as conversion_factor
//             // child.conversion_factor = res.message.conversion_factor; // Set conversion_factor
//           }

//           frm.refresh_field("items");
//           frm.set_value('custom_barcode', '');
//         } else {
//           return
//         }
//       },
//     });
//   },
// });



////////////////////////////////////END///////////////////////////////