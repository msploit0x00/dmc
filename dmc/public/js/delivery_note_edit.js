// // ============================
// // DELIVERY NOTE SCANNER - FIXED VERSION
// // ============================

// frappe.ui.form.on('Delivery Note', {
//     onload: function (frm) {
//         console.log('🚀 ONLOAD: Starting initialization...');

//         // Clear empty initial row
//         if (frm.is_new() && frm.doc.items && frm.doc.items.length == 1) {
//             if (!frm.doc.items[0].barcode && !frm.doc.items[0].item_code) {
//                 frm.clear_table("items");
//             }
//         }

//         // Initialize scanner state
//         frm._scanning = false;
//         frm._scan_queue = []; // NEW: Queue to handle rapid scans

//         // IMMEDIATE check for free scanner - no delay
//         check_and_toggle_free_scanner(frm);

//         // Also auto-add free items if creating from SO
//         auto_add_free_items_from_so(frm);
//     },

//     refresh: function (frm) {
//         console.log('🔄 REFRESH: Checking free scanner...');

//         // Check free scanner on every refresh
//         check_and_toggle_free_scanner(frm);

//         // Add button to manually link Sales Order if none found
//         if (!get_sales_order_reference(frm)) {
//             frm.add_custom_button(__('Link Sales Order'), function () {
//                 frappe.prompt({
//                     label: 'Sales Order',
//                     fieldname: 'sales_order',
//                     fieldtype: 'Link',
//                     options: 'Sales Order',
//                     reqd: 1
//                 }, function (values) {
//                     // Set SO reference in items
//                     if (frm.doc.items && frm.doc.items.length > 0) {
//                         frm.doc.items.forEach(item => {
//                             if (!item.against_sales_order) {
//                                 frappe.model.set_value(item.doctype, item.name, 'against_sales_order', values.sales_order);
//                             }
//                         });
//                     }

//                     // Also set document level if field exists
//                     if (frm.fields_dict.sales_order) {
//                         frm.set_value('sales_order', values.sales_order);
//                     }

//                     frappe.show_alert({
//                         message: __('Sales Order linked successfully'),
//                         indicator: 'green'
//                     });

//                     // Refresh to show free scanner
//                     setTimeout(() => {
//                         check_and_toggle_free_scanner(frm);
//                     }, 500);
//                 }, __('Link Sales Order'));
//             }, __('Actions'));
//         }
//     },

//     // REGULAR SCANNER - FIXED
//     custom_scan_barcodes: function (frm) {
//         if (!frm.doc.custom_scan_barcodes) return;

//         const barcode = frm.doc.custom_scan_barcodes;

//         // FIXED: Better scanning state management
//         if (frm._scanning) {
//             console.log('⏸️ Already scanning, queueing:', barcode);
//             frm._scan_queue = frm._scan_queue || [];
//             frm._scan_queue.push({ barcode: barcode, type: 'regular' });
//             frm.set_value('custom_scan_barcodes', '');
//             return;
//         }

//         frm._scanning = true;
//         console.log('📱 SCANNING REGULAR:', barcode);

//         frappe.call({
//             method: 'dmc.barcode_details.get_barcode_details',
//             args: { barcode: barcode },
//             async: false,
//             callback: function (response) {
//                 if (response.message) {
//                     const uom = response.message.barcode_uom[0]['uom'];
//                     const batchNo = response.message.batch_id;
//                     const itemCode = response.message.item_code[0]['parent'];
//                     const expiryDate = response.message.formatted_date;
//                     const conversionRate = response.message.conversion_factor[0]['conversion_factor'];
//                     const so_detail_id = response.message.so_detail_id;

//                     frappe.db.get_value('Item', itemCode, 'item_name', function (r) {
//                         const itemName = r.item_name;

//                         // FIXED: Look for existing row with EXACT match
//                         const existingRow = frm.doc.items.find(item => {
//                             const sameItem = item.item_code === itemCode;
//                             const sameBatch = item.batch_no === batchNo;
//                             const notFree = !item.is_free_item;

//                             console.log('🔍 Checking existing row:', {
//                                 checking: item.item_code,
//                                 sameItem,
//                                 sameBatch,
//                                 notFree,
//                                 is_free: item.is_free_item
//                             });

//                             return sameItem && sameBatch && notFree;
//                         });

//                         if (existingRow) {
//                             console.log('✅ FOUND EXISTING ROW - UPDATING');

//                             // FIXED: Store original values before any changes
//                             const originalRate = existingRow.rate;
//                             const originalUom = existingRow.uom;
//                             const originalConversionFactor = existingRow.conversion_factor;
//                             const currentQty = existingRow.qty || 0;
//                             const newQty = currentQty + 1;

//                             console.log('📊 UPDATE VALUES:', {
//                                 current_qty: currentQty,
//                                 new_qty: newQty,
//                                 original_rate: originalRate,
//                                 original_uom: originalUom,
//                                 original_conversion: originalConversionFactor
//                             });

//                             // CRITICAL: Use batch update to prevent field triggers from interfering
//                             frappe.model.set_value(existingRow.doctype, existingRow.name, {
//                                 'qty': newQty,
//                                 'custom_out_qty': newQty,
//                                 'barcode': barcode,
//                                 // FIXED: Force preserve original values
//                                 'uom': originalUom,
//                                 'conversion_factor': originalConversionFactor,
//                                 'rate': originalRate,
//                                 'amount': newQty * originalRate
//                             });

//                             // FIXED: Ensure SO details are maintained/set
//                             const salesOrder = get_sales_order_reference(frm);
//                             if (salesOrder) {
//                                 if (!existingRow.against_sales_order) {
//                                     frappe.model.set_value(existingRow.doctype, existingRow.name, 'against_sales_order', salesOrder);
//                                 }
//                                 // FIXED: Always ensure SO detail is set
//                                 set_so_detail(frm, existingRow, itemCode, so_detail_id, false);
//                             }

//                             console.log('✅ UPDATED ROW SUCCESSFULLY');
//                             finalize_scan(frm, `Updated quantity to ${newQty} for ${itemName}`, 'custom_scan_barcodes');

//                         } else {
//                             console.log('➕ CREATING NEW ROW');
//                             // Create new row
//                             let newRow = frm.add_child('items', {
//                                 item_code: itemCode,
//                                 item_name: itemName,
//                                 qty: 1,
//                                 custom_out_qty: 1,
//                                 uom: uom,
//                                 conversion_factor: conversionRate,
//                                 batch_no: batchNo,
//                                 custom_expiry_date: expiryDate,
//                                 barcode: barcode
//                             });

//                             // FIXED: Set SO references immediately
//                             const salesOrder = get_sales_order_reference(frm);
//                             if (salesOrder) {
//                                 frappe.model.set_value(newRow.doctype, newRow.name, 'against_sales_order', salesOrder);
//                                 set_so_detail(frm, newRow, itemCode, so_detail_id, false);
//                             }

//                             // CRITICAL: Let item_code trigger set the rate, then finalize
//                             frm.script_manager.trigger('item_code', newRow.doctype, newRow.name).then(() => {
//                                 console.log('🎯 ITEM CODE TRIGGERED - RATE SET');
//                                 finalize_scan(frm, `Added 1 ${uom} of ${itemName}`, 'custom_scan_barcodes');
//                             });
//                         }
//                     });
//                 } else {
//                     frappe.msgprint(__("Barcode not found"));
//                     finalize_scan(frm, "", 'custom_scan_barcodes');
//                 }
//             },
//             error: function () {
//                 console.log('❌ SCAN ERROR');
//                 finalize_scan(frm, "", 'custom_scan_barcodes');
//             }
//         });
//     },

//     // FREE ITEM SCANNER - FIXED
//     custom_scan_barcodes_for_free_items: function (frm) {
//         if (!frm.doc.custom_scan_barcodes_for_free_items) return;

//         const barcode = frm.doc.custom_scan_barcodes_for_free_items;

//         // FIXED: Better scanning state management
//         if (frm._scanning) {
//             console.log('⏸️ Already scanning free item, queueing:', barcode);
//             frm._scan_queue = frm._scan_queue || [];
//             frm._scan_queue.push({ barcode: barcode, type: 'free' });
//             frm.set_value('custom_scan_barcodes_for_free_items', '');
//             return;
//         }

//         frm._scanning = true;
//         console.log('🎁 SCANNING FREE ITEM:', barcode);

//         frappe.call({
//             method: 'dmc.barcode_details.get_barcode_details',
//             args: { barcode: barcode },
//             async: false,
//             callback: function (response) {
//                 if (response.message) {
//                     const uom = response.message.barcode_uom[0]['uom'];
//                     const batchNo = response.message.batch_id;
//                     const itemCode = response.message.item_code[0]['parent'];
//                     const expiryDate = response.message.formatted_date;
//                     const conversionRate = response.message.conversion_factor[0]['conversion_factor'];

//                     const salesOrder = get_sales_order_reference(frm);
//                     if (!salesOrder) {
//                         frappe.msgprint(__("No Sales Order found for free items"));
//                         finalize_scan(frm, "", 'custom_scan_barcodes_for_free_items');
//                         return;
//                     }

//                     check_if_item_is_free_in_sales_order(frm, itemCode, function (is_free, allowedQty) {
//                         if (!is_free) {
//                             frappe.msgprint(__("This item is not marked as free in the Sales Order. Please use the regular scanner."));
//                             finalize_scan(frm, "", 'custom_scan_barcodes_for_free_items');
//                             return;
//                         }

//                         // FIXED: Check for existing free row
//                         const existingFreeRow = frm.doc.items.find(item => {
//                             const sameItem = item.item_code === itemCode;
//                             const sameBatch = item.batch_no === batchNo;
//                             const isFree = item.is_free_item === 1;
//                             return sameItem && sameBatch && isFree;
//                         });

//                         // Calculate current total free quantity
//                         const currentFreeQty = frm.doc.items
//                             .filter(item => item.item_code === itemCode && item.is_free_item === 1)
//                             .reduce((total, item) => total + (item.qty || 0), 0);

//                         const newTotalQty = currentFreeQty + 1;
//                         if (newTotalQty > allowedQty) {
//                             frappe.msgprint({
//                                 title: __('Quantity Exceeded'),
//                                 message: __(`Cannot scan more free items. Current: ${currentFreeQty}, Allowed: ${allowedQty} for item ${itemCode}`),
//                                 indicator: 'red'
//                             });
//                             finalize_scan(frm, "", 'custom_scan_barcodes_for_free_items');
//                             return;
//                         }

//                         frappe.db.get_value('Item', itemCode, 'item_name', function (r) {
//                             const itemName = r.item_name;

//                             if (existingFreeRow) {
//                                 console.log('✅ UPDATING EXISTING FREE ROW');

//                                 const currentQty = existingFreeRow.qty || 0;
//                                 const newQty = currentQty + 1;

//                                 // FIXED: Batch update for free items
//                                 frappe.model.set_value(existingFreeRow.doctype, existingFreeRow.name, {
//                                     'qty': newQty,
//                                     'custom_out_qty': newQty,
//                                     'barcode': barcode,
//                                     'rate': 0,
//                                     'amount': 0
//                                 });

//                                 // FIXED: Ensure SO details for free items
//                                 if (!existingFreeRow.against_sales_order) {
//                                     frappe.model.set_value(existingFreeRow.doctype, existingFreeRow.name, 'against_sales_order', salesOrder);
//                                 }
//                                 set_so_detail(frm, existingFreeRow, itemCode, null, true);

//                                 finalize_free_scan(frm, `Updated free quantity to ${newQty} for ${itemName}`);

//                             } else {
//                                 console.log('➕ CREATING NEW FREE ROW');

//                                 let newRow = frm.add_child('items', {
//                                     item_code: itemCode,
//                                     item_name: itemName,
//                                     qty: 1,
//                                     custom_out_qty: 1,
//                                     uom: uom,
//                                     conversion_factor: conversionRate,
//                                     batch_no: batchNo,
//                                     custom_expiry_date: expiryDate,
//                                     barcode: barcode,
//                                     is_free_item: 1,
//                                     rate: 0,
//                                     amount: 0,
//                                     against_sales_order: salesOrder
//                                 });

//                                 // FIXED: Set SO detail immediately
//                                 set_so_detail(frm, newRow, itemCode, null, true);

//                                 finalize_free_scan(frm, `Added 1 free ${uom} of ${itemName}`);
//                             }
//                         });
//                     });
//                 } else {
//                     frappe.msgprint(__("Barcode not found"));
//                     finalize_scan(frm, "", 'custom_scan_barcodes_for_free_items');
//                 }
//             },
//             error: function () {
//                 console.log('❌ FREE SCAN ERROR');
//                 finalize_scan(frm, "", 'custom_scan_barcodes_for_free_items');
//             }
//         });
//     }
// });

// // ===========================
// // HELPER FUNCTIONS - ENHANCED
// // ===========================

// function get_sales_order_reference(frm) {
//     console.log('🔍 === SEARCHING FOR SALES ORDER REFERENCE ===');

//     // Method 1: Check document field first
//     if (frm.doc.sales_order) {
//         console.log('📋 Found SO in doc.sales_order:', frm.doc.sales_order);
//         return frm.doc.sales_order;
//     }

//     // Method 2: Check items table
//     if (frm.doc.items && frm.doc.items.length > 0) {
//         for (let item of frm.doc.items) {
//             if (item.against_sales_order) {
//                 console.log('📋 Found SO in items:', item.against_sales_order);
//                 return item.against_sales_order;
//             }
//         }
//     }

//     // Method 3: Check URL parameters (when creating DN from SO)
//     const urlParams = new URLSearchParams(window.location.search);
//     const fromSO = urlParams.get('sales_order');
//     if (fromSO) {
//         console.log('📋 Found SO in URL:', fromSO);
//         return fromSO;
//     }

//     // Method 4: Check if this DN was created from SO (check route history)
//     if (frappe.route_history && frappe.route_history.length > 1) {
//         const previousRoute = frappe.route_history[frappe.route_history.length - 2];
//         if (previousRoute && previousRoute[1] === 'Sales Order') {
//             const soName = previousRoute[2];
//             console.log('📋 Found SO in route history:', soName);
//             return soName;
//         }
//     }

//     // Method 5: Check frappe.route_options (set when creating from SO)
//     if (frappe.route_options && frappe.route_options.sales_order) {
//         console.log('📋 Found SO in route_options:', frappe.route_options.sales_order);
//         return frappe.route_options.sales_order;
//     }

//     // Method 6: For existing DN, check if it has items with SO references
//     if (!frm.is_new()) {
//         console.log('📋 Existing DN: Re-checking items for SO references...');
//         frm.refresh();
//         if (frm.doc.items && frm.doc.items.length > 0) {
//             for (let item of frm.doc.items) {
//                 if (item.against_sales_order) {
//                     console.log('📋 Found SO in refreshed items:', item.against_sales_order);
//                     return item.against_sales_order;
//                 }
//             }
//         }
//     }

//     console.log('❌ No Sales Order reference found after all methods');
//     console.log('🔍 Debug info:', {
//         doc_sales_order: frm.doc.sales_order,
//         items_count: frm.doc.items ? frm.doc.items.length : 0,
//         url_params: window.location.search,
//         route_options: frappe.route_options,
//         is_new: frm.is_new()
//     });

//     return null;
// }

// function check_and_toggle_free_scanner(frm) {
//     console.log('🔍 === CHECKING FREE SCANNER VISIBILITY ===');

//     const salesOrder = get_sales_order_reference(frm);
//     console.log('📋 Sales Order found:', salesOrder);

//     if (!salesOrder) {
//         console.log('❌ No Sales Order, hiding free scanner');
//         hide_free_scanner(frm);
//         return;
//     }

//     frappe.call({
//         method: "frappe.client.get",
//         args: {
//             doctype: "Sales Order",
//             name: salesOrder
//         },
//         callback: function (response) {
//             if (response.message && response.message.items) {
//                 const freeItems = response.message.items.filter(item => {
//                     const standardFree = item.is_free_item === 1 || item.is_free_item === "1" || item.is_free_item === true;
//                     const customFree = item.custom_is_free_item === 1 || item.custom_is_free_item === "1" || item.custom_is_free_item === true;
//                     return standardFree || customFree;
//                 });

//                 console.log('🎁 TOTAL FREE ITEMS FOUND:', freeItems.length);

//                 if (freeItems.length > 0) {
//                     console.log('✅ FREE ITEMS EXIST - SHOWING SCANNER');
//                     show_free_scanner(frm, freeItems.length);
//                 } else {
//                     console.log('❌ NO FREE ITEMS - HIDING SCANNER');
//                     hide_free_scanner(frm);
//                 }
//             } else {
//                 console.log('❌ No Sales Order data or items found');
//                 hide_free_scanner(frm);
//             }
//         },
//         error: function (err) {
//             console.log('❌ Error fetching Sales Order:', err);
//             hide_free_scanner(frm);
//         }
//     });
// }

// function show_free_scanner(frm, freeItemsCount) {
//     console.log('🎁 SHOWING FREE SCANNER with', freeItemsCount, 'free items');
//     frm.set_df_property('custom_scan_barcodes_for_free_items', 'hidden', 0);
//     frm.toggle_display('custom_scan_barcodes_for_free_items', true);
//     frm.set_df_property('custom_scan_barcodes_for_free_items', 'description',
//         `🎁 Free Item Scanner (${freeItemsCount} free items available)`);
//     frm.refresh_field('custom_scan_barcodes_for_free_items');
// }

// function hide_free_scanner(frm) {
//     console.log('❌ HIDING FREE SCANNER');
//     frm.toggle_display('custom_scan_barcodes_for_free_items', false);
//     frm.set_df_property('custom_scan_barcodes_for_free_items', 'hidden', 1);
// }

// function auto_add_free_items_from_so(frm) {
//     const salesOrder = get_sales_order_reference(frm);
//     if (!salesOrder || !frm.is_new()) {
//         return;
//     }

//     frappe.call({
//         method: "frappe.client.get",
//         args: {
//             doctype: "Sales Order",
//             name: salesOrder
//         },
//         callback: function (response) {
//             if (response.message && response.message.items) {
//                 const freeItems = response.message.items.filter(item =>
//                     item.is_free_item === 1 || item.custom_is_free_item === 1
//                 );

//                 freeItems.forEach(soItem => {
//                     const existingItem = frm.doc.items.find(dnItem =>
//                         dnItem.item_code === soItem.item_code &&
//                         dnItem.is_free_item === 1
//                     );

//                     if (!existingItem && soItem.qty > 0) {
//                         let newRow = frm.add_child('items', {
//                             item_code: soItem.item_code,
//                             item_name: soItem.item_name,
//                             qty: 0,
//                             custom_out_qty: 0,
//                             uom: soItem.uom,
//                             conversion_factor: soItem.conversion_factor || 1,
//                             is_free_item: 1,
//                             rate: 0,
//                             amount: 0,
//                             against_sales_order: salesOrder,
//                             so_detail: soItem.name
//                         });
//                     }
//                 });

//                 if (freeItems.length > 0) {
//                     frm.refresh_field('items');
//                 }
//             }
//         }
//     });
// }

// function check_if_item_is_free_in_sales_order(frm, itemCode, callback) {
//     const salesOrder = get_sales_order_reference(frm);

//     if (!salesOrder) {
//         callback(false, 0);
//         return;
//     }

//     frappe.call({
//         method: "frappe.client.get",
//         args: {
//             doctype: "Sales Order",
//             name: salesOrder
//         },
//         callback: function (response) {
//             if (response.message && response.message.items) {
//                 const freeItem = response.message.items.find(item =>
//                     item.item_code === itemCode &&
//                     (item.is_free_item === 1 || item.is_free_item === "1" || item.is_free_item === true ||
//                         item.custom_is_free_item === 1 || item.custom_is_free_item === "1" || item.custom_is_free_item === true)
//                 );

//                 callback(!!freeItem, freeItem ? freeItem.qty : 0);
//             } else {
//                 callback(false, 0);
//             }
//         }
//     });
// }

// // FIXED: Enhanced SO detail setting with better error handling
// function set_so_detail(frm, row, itemCode, so_detail_id, is_free_item) {
//     const salesOrder = get_sales_order_reference(frm);
//     if (!salesOrder) {
//         console.log('❌ No Sales Order for SO detail setting');
//         return;
//     }

//     console.log('🔗 Setting SO detail:', {
//         item: itemCode,
//         so_detail_id: so_detail_id,
//         is_free: is_free_item,
//         row_name: row.name
//     });

//     if (so_detail_id) {
//         // Use provided SO detail ID
//         frappe.model.set_value(row.doctype, row.name, 'so_detail', so_detail_id);
//         console.log('✅ Set SO detail from barcode response:', so_detail_id);
//     } else {
//         // Find matching item in Sales Order
//         frappe.call({
//             method: "frappe.client.get",
//             args: {
//                 doctype: "Sales Order",
//                 name: salesOrder
//             },
//             callback: function (response) {
//                 if (response.message && response.message.items) {
//                     let soItem;

//                     if (is_free_item) {
//                         // For free items, find the free item match
//                         soItem = response.message.items.find(item =>
//                             item.item_code === itemCode &&
//                             (item.is_free_item === 1 || item.custom_is_free_item === 1)
//                         );
//                     } else {
//                         // For regular items, find non-free item match
//                         soItem = response.message.items.find(item =>
//                             item.item_code === itemCode &&
//                             !item.is_free_item && !item.custom_is_free_item
//                         );
//                     }

//                     if (soItem) {
//                         frappe.model.set_value(row.doctype, row.name, 'so_detail', soItem.name);
//                         console.log('✅ Found and set SO detail:', soItem.name);
//                     } else {
//                         console.log('⚠️ No matching SO item found for:', itemCode);
//                     }
//                 } else {
//                     console.log('❌ Could not fetch SO details');
//                 }
//             }
//         });
//     }
// }

// function clear_barcode_field(frm, field_name) {
//     frm.set_value(field_name, '');
// }

// // FIXED: Enhanced finalize_scan with queue processing
// function finalize_scan(frm, message, field_name) {
//     console.log('🏁 FINALIZING SCAN');

//     // Clear barcode field first
//     clear_barcode_field(frm, field_name);

//     // Refresh items table
//     frm.refresh_field('items');

//     // Calculate totals
//     frm.script_manager.trigger("calculate_taxes_and_totals");

//     if (message) {
//         frappe.show_alert({
//             message: __(message),
//             indicator: 'green'
//         });
//     }

//     // FIXED: Reset scanning state and process queue
//     setTimeout(() => {
//         frm._scanning = false;
//         process_scan_queue(frm);
//     }, 300);
// }

// function finalize_free_scan(frm, message) {
//     console.log('🏁 FINALIZING FREE SCAN');

//     clear_barcode_field(frm, 'custom_scan_barcodes_for_free_items');

//     // Ensure all free items stay at rate 0
//     frm.doc.items.forEach(item => {
//         if (item.is_free_item === 1) {
//             frappe.model.set_value(item.doctype, item.name, 'rate', 0);
//             frappe.model.set_value(item.doctype, item.name, 'amount', 0);
//         }
//     });

//     frm.refresh_field('items');
//     frm.script_manager.trigger("calculate_taxes_and_totals");

//     if (message) {
//         frappe.show_alert({
//             message: __(message),
//             indicator: 'blue'
//         });
//     }

//     // Reset scanning state and process queue
//     setTimeout(() => {
//         frm._scanning = false;
//         process_scan_queue(frm);
//     }, 300);
// }

// // NEW: Process queued scans
// function process_scan_queue(frm) {
//     if (!frm._scan_queue || frm._scan_queue.length === 0) {
//         return;
//     }

//     console.log('📦 Processing scan queue, items:', frm._scan_queue.length);

//     const nextScan = frm._scan_queue.shift();

//     if (nextScan.type === 'regular') {
//         frm.set_value('custom_scan_barcodes', nextScan.barcode);
//     } else if (nextScan.type === 'free') {
//         frm.set_value('custom_scan_barcodes_for_free_items', nextScan.barcode);
//     }
// }

// // ===========================
// // DELIVERY NOTE ITEM EVENTS - ENHANCED
// // ===========================

// frappe.ui.form.on('Delivery Note Item', {
//     custom_out_qty: function (frm, cdt, cdn) {
//         const row = locals[cdt][cdn];

//         if (row.custom_out_qty !== row.qty) {
//             frappe.model.set_value(cdt, cdn, 'qty', row.custom_out_qty || 0);
//         }

//         if (row.is_free_item === 1) {
//             frappe.model.set_value(cdt, cdn, 'rate', 0);
//             frappe.model.set_value(cdt, cdn, 'amount', 0);
//         }
//     },

//     rate: function (frm, cdt, cdn) {
//         const row = locals[cdt][cdn];

//         if (row.is_free_item === 1 && row.rate !== 0) {
//             frappe.model.set_value(cdt, cdn, 'rate', 0);
//             frappe.model.set_value(cdt, cdn, 'amount', 0);
//         }
//     },

//     item_code: function (frm, cdt, cdn) {
//         const row = locals[cdt][cdn];

//         if (row.is_free_item === 1) {
//             frappe.model.set_value(cdt, cdn, 'rate', 0);
//             frappe.model.set_value(cdt, cdn, 'amount', 0);
//         }

//         if (row.qty && !row.custom_out_qty) {
//             frappe.model.set_value(cdt, cdn, 'custom_out_qty', row.qty);
//         }
//     },

//     qty: function (frm, cdt, cdn) {
//         const row = locals[cdt][cdn];

//         if (row.is_free_item === 1) {
//             frappe.model.set_value(cdt, cdn, 'rate', 0);
//             frappe.model.set_value(cdt, cdn, 'amount', 0);
//         }

//         if (row.qty !== row.custom_out_qty) {
//             frappe.model.set_value(cdt, cdn, 'custom_out_qty', row.qty || 0);
//         }
//     }
// });

// ============================
// DELIVERY NOTE SCANNER - USB SCANNER OPTIMIZED VERSION
// ============================

frappe.ui.form.on('Delivery Note', {
    // onload: function (frm) {
    //     console.log('🚀 ONLOAD: Starting initialization...');

    //     // Clear empty initial row
    //     if (frm.is_new() && frm.doc.items && frm.doc.items.length == 1) {
    //         if (!frm.doc.items[0].barcode && !frm.doc.items[0].item_code) {
    //             frm.clear_table("items");
    //         }
    //     }

    //     // Initialize scanner state with enhanced timing
    //     frm._scanning = false;
    //     frm._scan_queue = [];
    //     frm._scan_timeout = null; // NEW: Timeout handler for delayed processing
    //     frm._last_scan_time = 0; // NEW: Track last scan time

    //     // IMMEDIATE check for free scanner - no delay
    //     check_and_toggle_free_scanner(frm);

    //     // Also auto-add free items if creating from SO
    //     auto_add_free_items_from_so(frm);
    // },
    onload: function (frm) {
        console.log('🚀 ONLOAD: Starting initialization...');

        // Clear empty initial row
        if (frm.is_new() && frm.doc.items && frm.doc.items.length == 1) {
            if (!frm.doc.items[0].barcode && !frm.doc.items[0].item_code) {
                frm.clear_table("items");
            }
        }

        // ENHANCED: Initialize scanner state with better tracking
        frm._scanning = false;
        frm._scan_queue = [];
        frm._scan_timeout = null;
        frm._last_scan_time = 0;
        frm._last_free_scan_time = 0;

        // NEW: Track processed barcodes to prevent duplicates
        frm._processed_barcodes = new Set();
        frm._processed_free_barcodes = new Set();

        check_and_toggle_free_scanner(frm);
        auto_add_free_items_from_so(frm);
    },
    refresh: function (frm) {
        console.log('🔄 REFRESH: Checking free scanner...');

        // Check free scanner on every refresh
        check_and_toggle_free_scanner(frm);

        // Add button to manually link Sales Order if none found
        if (!get_sales_order_reference(frm)) {
            frm.add_custom_button(__('Link Sales Order'), function () {
                frappe.prompt({
                    label: 'Sales Order',
                    fieldname: 'sales_order',
                    fieldtype: 'Link',
                    options: 'Sales Order',
                    reqd: 1
                }, function (values) {
                    // Set SO reference in items
                    if (frm.doc.items && frm.doc.items.length > 0) {
                        frm.doc.items.forEach(item => {
                            if (!item.against_sales_order) {
                                frappe.model.set_value(item.doctype, item.name, 'against_sales_order', values.sales_order);
                            }
                        });
                    }

                    // Also set document level if field exists
                    if (frm.fields_dict.sales_order) {
                        frm.set_value('sales_order', values.sales_order);
                    }

                    frappe.show_alert({
                        message: __('Sales Order linked successfully'),
                        indicator: 'green'
                    });

                    // Refresh to show free scanner
                    setTimeout(() => {
                        check_and_toggle_free_scanner(frm);
                    }, 500);
                }, __('Link Sales Order'));
            }, __('Actions'));
        }
    },

    // REGULAR SCANNER - USB SCANNER OPTIMIZED
    custom_scan_barcodes: function (frm) {
        if (!frm.doc.custom_scan_barcodes) return;

        const barcode = frm.doc.custom_scan_barcodes.trim();
        const currentTime = Date.now();

        console.log('📱 SCAN INPUT DETECTED:', barcode, 'Time:', currentTime);

        // Enhanced validation for complete barcodes
        if (!is_complete_barcode(barcode)) {
            console.log('⏸️ Incomplete barcode detected');
            return;
        }

        // CRITICAL FIX: Check if this exact barcode is currently being processed
        if (frm._scanning && frm._current_processing_barcode === barcode) {
            console.log('🚫 DUPLICATE DETECTED: Same barcode already processing:', barcode);
            // Clear the field immediately to prevent re-triggering
            frm.set_value('custom_scan_barcodes', '');
            return;
        }

        // ENHANCED: Time-based debouncing with processed barcode tracking
        const barcodeKey = `${barcode}_${Date.now()}`;
        if (frm._processed_barcodes.has(barcode) &&
            (currentTime - frm._last_scan_time) < 3000) { // 3 second window
            console.log('🚫 DUPLICATE PREVENTED: Barcode recently processed:', barcode);
            frm.set_value('custom_scan_barcodes', '');
            return;
        }

        // Update tracking
        frm._last_scan_time = currentTime;
        frm._current_processing_barcode = barcode;

        // Clear any existing timeout
        if (frm._scan_timeout) {
            clearTimeout(frm._scan_timeout);
            frm._scan_timeout = null;
        }

        // Add to processed set
        frm._processed_barcodes.add(barcode);

        // Clean up old processed barcodes (keep only recent ones)
        setTimeout(() => {
            frm._processed_barcodes.delete(barcode);
        }, 5000); // Remove after 5 seconds

        console.log('✅ PROCESSING BARCODE:', barcode);

        // Process immediately, no delay
        process_regular_scan_fixed(frm, barcode);
    },

    // FIXED: FREE SCANNER with same logic
    custom_scan_barcodes_for_free_items: function (frm) {
        if (!frm.doc.custom_scan_barcodes_for_free_items) return;

        const barcode = frm.doc.custom_scan_barcodes_for_free_items.trim();
        const currentTime = Date.now();

        if (!is_complete_barcode(barcode)) {
            return;
        }

        // Same duplicate prevention for free items
        if (frm._scanning && frm._current_processing_free_barcode === barcode) {
            console.log('🚫 DUPLICATE FREE SCAN PREVENTED:', barcode);
            frm.set_value('custom_scan_barcodes_for_free_items', '');
            return;
        }

        if (frm._processed_free_barcodes.has(barcode) &&
            (currentTime - frm._last_free_scan_time) < 3000) {
            console.log('🚫 FREE DUPLICATE PREVENTED:', barcode);
            frm.set_value('custom_scan_barcodes_for_free_items', '');
            return;
        }

        frm._last_free_scan_time = currentTime;
        frm._current_processing_free_barcode = barcode;
        frm._processed_free_barcodes.add(barcode);

        setTimeout(() => {
            frm._processed_free_barcodes.delete(barcode);
        }, 5000);

        process_free_scan(frm, barcode);
    }
    // custom_scan_barcodes: function (frm) {
    //     if (!frm.doc.custom_scan_barcodes) return;

    //     const barcode = frm.doc.custom_scan_barcodes.trim();
    //     const currentTime = Date.now();

    //     console.log('📱 SCAN INPUT DETECTED:', barcode, 'Length:', barcode.length);

    //     // NEW: Enhanced validation for complete barcodes
    //     if (!is_complete_barcode(barcode)) {
    //         console.log('⏸️ Incomplete barcode detected, waiting for more input...');
    //         return; // Don't process incomplete barcodes
    //     }

    //     // NEW: Debounce rapid scans from USB scanners
    //     if (frm._last_scan_time && (currentTime - frm._last_scan_time) < 100) {
    //         console.log('⏸️ Too rapid scan detected, ignoring duplicate');
    //         return;
    //     }

    //     frm._last_scan_time = currentTime;

    //     // Clear any existing timeout
    //     if (frm._scan_timeout) {
    //         clearTimeout(frm._scan_timeout);
    //         frm._scan_timeout = null;
    //     }

    //     // NEW: Delayed processing to ensure complete barcode capture
    //     frm._scan_timeout = setTimeout(() => {
    //         process_regular_scan(frm, barcode);
    //     }, 200); // 200ms delay to ensure complete input
    // },

    // // FREE ITEM SCANNER - USB SCANNER OPTIMIZED
    // custom_scan_barcodes_for_free_items: function (frm) {
    //     if (!frm.doc.custom_scan_barcodes_for_free_items) return;

    //     const barcode = frm.doc.custom_scan_barcodes_for_free_items.trim();
    //     const currentTime = Date.now();

    //     console.log('🎁 FREE SCAN INPUT DETECTED:', barcode, 'Length:', barcode.length);

    //     // NEW: Enhanced validation for complete barcodes
    //     if (!is_complete_barcode(barcode)) {
    //         console.log('⏸️ Incomplete free barcode detected, waiting for more input...');
    //         return;
    //     }

    //     // NEW: Debounce rapid scans
    //     if (frm._last_scan_time && (currentTime - frm._last_scan_time) < 100) {
    //         console.log('⏸️ Too rapid free scan detected, ignoring duplicate');
    //         return;
    //     }

    //     frm._last_scan_time = currentTime;

    //     // Clear any existing timeout
    //     if (frm._scan_timeout) {
    //         clearTimeout(frm._scan_timeout);
    //         frm._scan_timeout = null;
    //     }

    //     // NEW: Delayed processing for free items
    //     frm._scan_timeout = setTimeout(() => {
    //         process_free_scan(frm, barcode);
    //     }, 200);
    // }
});

// ===========================
// NEW: BARCODE VALIDATION FUNCTIONS
// ===========================

function is_complete_barcode(barcode) {
    if (!barcode || barcode.length < 5) {
        return false; // Too short to be a valid barcode
    }

    // Check for common incomplete patterns
    if (barcode.includes('undefined') || barcode.includes('null')) {
        return false;
    }

    // Add more validation as needed based on your barcode format
    // Example: Check if barcode matches expected format/length

    return true;
}

// NEW: Function to identify barcode type and details
function are_related_barcodes(barcode1, barcode2) {
    if (!barcode1 || !barcode2) return false;

    const info1 = get_barcode_info(barcode1);
    const info2 = get_barcode_info(barcode2);

    // They are related if they have the same base part (same physical item)
    // regardless of packaging type (unit/box/carton)
    return info1.base === info2.base;
}

// Enhanced barcode info function
function get_barcode_info(barcode) {
    if (!barcode || barcode.length < 3) {
        return { type: 'unknown', prefix: '', base: barcode };
    }

    const prefix = barcode.substring(0, 3);
    const base = barcode.substring(3);

    let type = 'unknown';
    let packaging = 'unit';

    if (prefix === '010') {
        type = 'unit';
        packaging = 'unit';
    } else if (prefix === '011') {
        type = 'box';
        packaging = 'box';
    } else if (prefix === '012') {
        type = 'carton';
        packaging = 'carton';
    }

    return { type, prefix, base, packaging };
}
// function get_barcode_info(barcode) {
//     if (!barcode || barcode.length < 3) {
//         return { type: 'unknown', prefix: '', base: barcode };
//     }

//     const prefix = barcode.substring(0, 3);
//     const base = barcode.substring(3);

//     let type = 'unknown';
//     if (prefix === '010') {
//         type = 'unit';
//     } else if (prefix === '011') {
//         type = 'box';
//     } else if (prefix === '012') {
//         type = 'carton';
//     }

//     return { type, prefix, base };
// }

// // NEW: Function to check if two barcodes are for the same physical item
// function are_related_barcodes(barcode1, barcode2) {
//     const info1 = get_barcode_info(barcode1);
//     const info2 = get_barcode_info(barcode2);

//     // They are related if they have the same base part but different prefixes
//     return info1.base === info2.base && info1.prefix !== info2.prefix;
// }

// ===========================
// ENHANCED PROCESSING FUNCTIONS
// ===========================

// function process_regular_scan(frm, barcode) {
//     console.log('🔄 PROCESSING REGULAR SCAN:', barcode);

//     // Check if already processing
//     if (frm._scanning) {
//         console.log('⏸️ Already scanning, queueing:', barcode);
//         frm._scan_queue = frm._scan_queue || [];
//         frm._scan_queue.push({ barcode: barcode, type: 'regular' });
//         // DON'T clear the field immediately, let the current scan finish
//         return;
//     }

//     frm._scanning = true;

//     frappe.call({
//         method: 'dmc.barcode_details.get_barcode_details',
//         args: { barcode: barcode },
//         callback: function (response) {
//             if (response.message) {
//                 const uom = response.message.barcode_uom[0]['uom'];
//                 const batchNo = response.message.batch_id;
//                 const itemCode = response.message.item_code[0]['parent'];
//                 const expiryDate = response.message.formatted_date;
//                 const conversionRate = response.message.conversion_factor[0]['conversion_factor'];
//                 const so_detail_id = response.message.so_detail_id;

//                 frappe.db.get_value('Item', itemCode, 'item_name', function (r) {
//                     const itemName = r.item_name;

//                     console.log('🏷️ BARCODE ANALYSIS:', {
//                         scanned_barcode: barcode,
//                         barcode_info: get_barcode_info(barcode),
//                         item_code: itemCode,
//                         batch_no: batchNo,
//                         uom: uom,
//                         conversion_rate: conversionRate
//                     });

//                     // Look for existing row with EXACT match (item, batch, UOM, and barcode prefix)
//                     const existingRow = frm.doc.items.find(item => {
//                         const sameItem = item.item_code === itemCode;
//                         const sameBatch = item.batch_no === batchNo;
//                         const sameUom = item.uom === uom;
//                         const notFree = !item.is_free_item;

//                         // NEW: Allow same item/batch/uom even with different barcode types
//                         const isCompatible = sameItem && sameBatch && sameUom && notFree;

//                         console.log('🔍 Checking existing row:', {
//                             row_idx: item.idx,
//                             existing_barcode: item.barcode,
//                             existing_barcode_info: get_barcode_info(item.barcode || ''),
//                             current_barcode: barcode,
//                             current_barcode_info: get_barcode_info(barcode),
//                             existing_uom: item.uom,
//                             current_uom: uom,
//                             sameItem,
//                             sameBatch,
//                             sameUom,
//                             notFree,
//                             isCompatible,
//                             are_related: are_related_barcodes(item.barcode || '', barcode)
//                         });

//                         return isCompatible;
//                     });


//                     // const existingRow = frm.doc.items.find(item => {
//                     //     const sameItem = item.item_code === itemCode;
//                     //     const sameBatch = item.batch_no === batchNo;
//                     //     const sameUom = item.uom === uom;
//                     //     const sameBarcode = item.barcode === barcode;
//                     //     const notFree = !item.is_free_item;

//                     //     console.log('🔍 Checking existing row:', {
//                     //         row_idx: item.idx,
//                     //         existing_barcode: item.barcode,
//                     //         existing_uom: item.uom,
//                     //         current_barcode: barcode,
//                     //         current_uom: uom,
//                     //         sameItem,
//                     //         sameBatch,
//                     //         sameUom,
//                     //         sameBarcode,
//                     //         notFree,
//                     //         related_barcodes: are_related_barcodes(item.barcode || '', barcode)
//                     //     });

//                     //     return sameItem && sameBatch && sameUom && sameBarcode && notFree;
//                     // });

//                     if (existingRow) {
//                         console.log('✅ FOUND EXISTING ROW - UPDATING');

//                         const originalRate = existingRow.rate;
//                         const originalUom = existingRow.uom;
//                         const originalConversionFactor = existingRow.conversion_factor;
//                         const currentQty = existingRow.qty || 0;
//                         const newQty = currentQty + 1;

//                         // Use batch update to prevent field triggers
//                         frappe.model.set_value(existingRow.doctype, existingRow.name, {
//                             'qty': newQty,
//                             'custom_out_qty': newQty,
//                             'barcode': barcode,
//                             'uom': originalUom,
//                             'conversion_factor': originalConversionFactor,
//                             'rate': originalRate,
//                             'amount': newQty * originalRate
//                         });

//                         // Ensure SO details are maintained
//                         const salesOrder = get_sales_order_reference(frm);
//                         if (salesOrder) {
//                             if (!existingRow.against_sales_order) {
//                                 frappe.model.set_value(existingRow.doctype, existingRow.name, 'against_sales_order', salesOrder);
//                             }
//                             set_so_detail(frm, existingRow, itemCode, so_detail_id, false);
//                         }

//                         finalize_scan(frm, `Updated quantity to ${newQty} for ${itemName}`, 'custom_scan_barcodes');

//                     } else {
//                         console.log('➕ CREATING NEW ROW');

//                         let newRow = frm.add_child('items', {
//                             item_code: itemCode,
//                             item_name: itemName,
//                             qty: 1,
//                             custom_out_qty: 1,
//                             uom: uom,
//                             conversion_factor: conversionRate,
//                             batch_no: batchNo,
//                             custom_expiry_date: expiryDate,
//                             barcode: barcode
//                         });

//                         // Set SO references immediately
//                         const salesOrder = get_sales_order_reference(frm);
//                         if (salesOrder) {
//                             frappe.model.set_value(newRow.doctype, newRow.name, 'against_sales_order', salesOrder);
//                             set_so_detail(frm, newRow, itemCode, so_detail_id, false);
//                         }

//                         // Let item_code trigger set the rate, then finalize
//                         frm.script_manager.trigger('item_code', newRow.doctype, newRow.name).then(() => {
//                             console.log('🎯 ITEM CODE TRIGGERED - RATE SET');
//                             finalize_scan(frm, `Added 1 ${uom} of ${itemName}`, 'custom_scan_barcodes');
//                         });
//                     }
//                 });
//             } else {
//                 frappe.msgprint(__("Barcode not found"));
//                 finalize_scan(frm, "", 'custom_scan_barcodes');
//             }
//         },
//         error: function () {
//             console.log('❌ SCAN ERROR');
//             finalize_scan(frm, "", 'custom_scan_barcodes');
//         }
//     });
// }


function process_regular_scan_fixed(frm, barcode) {
    console.log('🔄 PROCESSING REGULAR SCAN - SINGLE RUN:', barcode);

    // CRITICAL: Immediate field clear to prevent re-triggering
    frm.set_value('custom_scan_barcodes', '');

    // Check if already processing ANY scan
    if (frm._scanning) {
        console.log('⏸️ Already scanning another item, queueing:', barcode);
        frm._scan_queue = frm._scan_queue || [];
        frm._scan_queue.push({ barcode: barcode, type: 'regular' });
        return;
    }

    frm._scanning = true;

    frappe.call({
        method: 'dmc.barcode_details.get_barcode_details',
        args: { barcode: barcode },
        callback: function (response) {
            if (response.message) {
                const uom = response.message.barcode_uom[0]['uom'];
                const batchNo = response.message.batch_id;
                const itemCode = response.message.item_code[0]['parent'];
                const expiryDate = response.message.formatted_date;
                const conversionRate = response.message.conversion_factor[0]['conversion_factor'];
                const so_detail_id = response.message.so_detail_id;

                frappe.db.get_value('Item', itemCode, 'item_name', function (r) {
                    const itemName = r.item_name;

                    // Look for existing row
                    const existingRow = frm.doc.items.find(item => {
                        const sameItem = item.item_code === itemCode;
                        const sameBatch = item.batch_no === batchNo;
                        const sameUom = item.uom === uom;
                        const notFree = !item.is_free_item;
                        return sameItem && sameBatch && sameUom && notFree;
                    });

                    if (existingRow) {
                        console.log('✅ UPDATING EXISTING ROW - SINGLE EXECUTION');

                        const currentQty = existingRow.qty || 0;
                        const newQty = currentQty + 1;

                        console.log(`📊 QTY UPDATE: ${currentQty} → ${newQty}`);

                        // SAFE UPDATE: Use direct assignment to prevent triggers
                        existingRow.qty = newQty;
                        existingRow.custom_out_qty = newQty;
                        existingRow.barcode = barcode;
                        existingRow.amount = newQty * (existingRow.rate || 0);

                        // Manual refresh
                        frm.refresh_field('items');

                        // Set SO details if needed
                        const salesOrder = get_sales_order_reference(frm);
                        if (salesOrder && !existingRow.against_sales_order) {
                            existingRow.against_sales_order = salesOrder;
                            set_so_detail(frm, existingRow, itemCode, so_detail_id, false);
                        }

                        finalize_scan_fixed(frm, `Updated quantity to ${newQty} for ${itemName}`);

                    } else {
                        console.log('➕ CREATING NEW ROW - SINGLE EXECUTION');

                        let newRow = frm.add_child('items', {
                            item_code: itemCode,
                            item_name: itemName,
                            qty: 1,
                            custom_out_qty: 1,
                            uom: uom,
                            conversion_factor: conversionRate,
                            batch_no: batchNo,
                            custom_expiry_date: expiryDate,
                            barcode: barcode
                        });

                        const salesOrder = get_sales_order_reference(frm);
                        if (salesOrder) {
                            newRow.against_sales_order = salesOrder;
                            set_so_detail(frm, newRow, itemCode, so_detail_id, false);
                        }

                        frm.script_manager.trigger('item_code', newRow.doctype, newRow.name).then(() => {
                            finalize_scan_fixed(frm, `Added 1 ${uom} of ${itemName}`);
                        });
                    }
                });
            } else {
                frappe.msgprint(__("Barcode not found"));
                finalize_scan_fixed(frm, "");
            }
        },
        error: function () {
            console.log('❌ SCAN ERROR');
            finalize_scan_fixed(frm, "");
        }
    });
}

// ===========================
// FIXED FINALIZE FUNCTION
// ===========================

function finalize_scan_fixed(frm, message) {
    console.log('🏁 FINALIZING SCAN - SINGLE EXECUTION');

    // Do NOT clear barcode field here - already cleared at start

    // Refresh and calculate
    frm.refresh_field('items');
    frm.script_manager.trigger("calculate_taxes_and_totals");

    if (message) {
        frappe.show_alert({
            message: __(message),
            indicator: 'green'
        });
    }

    // Reset state
    frm._scanning = false;
    frm._current_processing_barcode = null;

    // Process queue if any
    setTimeout(() => {
        process_scan_queue(frm);
    }, 100);
}

// ===========================
// DEBUGGING VERSION
// ===========================

function process_regular_scan_debug(frm, barcode) {
    const timestamp = new Date().toISOString();
    const callId = Math.random().toString(36).substr(2, 9);

    console.log(`🔍 SCAN CALL #${callId} at ${timestamp}:`, barcode);

    // Add a global counter to track calls
    window.scanCallCount = (window.scanCallCount || 0) + 1;
    console.log(`📊 TOTAL SCAN CALLS: ${window.scanCallCount}`);

    // Rest of your processing logic...
}
function process_free_scan(frm, barcode) {
    console.log('🔄 PROCESSING FREE SCAN:', barcode);

    // Check if already processing
    if (frm._scanning) {
        console.log('⏸️ Already scanning free item, queueing:', barcode);
        frm._scan_queue = frm._scan_queue || [];
        frm._scan_queue.push({ barcode: barcode, type: 'free' });
        return;
    }

    frm._scanning = true;

    frappe.call({
        method: 'dmc.barcode_details.get_barcode_details',
        args: { barcode: barcode },
        callback: function (response) {
            if (response.message) {
                const uom = response.message.barcode_uom[0]['uom'];
                const batchNo = response.message.batch_id;
                const itemCode = response.message.item_code[0]['parent'];
                const expiryDate = response.message.formatted_date;
                const conversionRate = response.message.conversion_factor[0]['conversion_factor'];

                const salesOrder = get_sales_order_reference(frm);
                if (!salesOrder) {
                    frappe.msgprint(__("No Sales Order found for free items"));
                    finalize_scan(frm, "", 'custom_scan_barcodes_for_free_items');
                    return;
                }

                check_if_item_is_free_in_sales_order(frm, itemCode, function (is_free, allowedQty) {
                    if (!is_free) {
                        frappe.msgprint(__("This item is not marked as free in the Sales Order. Please use the regular scanner."));
                        finalize_scan(frm, "", 'custom_scan_barcodes_for_free_items');
                        return;
                    }

                    // Check for existing free row with EXACT match (item, batch, UOM, and barcode)
                    const existingFreeRow = frm.doc.items.find(item => {
                        const sameItem = item.item_code === itemCode;
                        const sameBatch = item.batch_no === batchNo;
                        const sameUom = item.uom === uom;
                        const sameBarcode = item.barcode === barcode;
                        const isFree = item.is_free_item === 1;

                        console.log('🔍 Checking existing free row:', {
                            checking_barcode: item.barcode,
                            current_barcode: barcode,
                            checking_uom: item.uom,
                            current_uom: uom,
                            sameItem,
                            sameBatch,
                            sameUom,
                            sameBarcode,
                            isFree
                        });

                        return sameItem && sameBatch && sameUom && sameBarcode && isFree;
                    });

                    // Calculate current total free quantity
                    const currentFreeQty = frm.doc.items
                        .filter(item => item.item_code === itemCode && item.is_free_item === 1)
                        .reduce((total, item) => total + (item.qty || 0), 0);

                    const newTotalQty = currentFreeQty + 1;
                    if (newTotalQty > allowedQty) {
                        frappe.msgprint({
                            title: __('Quantity Exceeded'),
                            message: __(`Cannot scan more free items. Current: ${currentFreeQty}, Allowed: ${allowedQty} for item ${itemCode}`),
                            indicator: 'red'
                        });
                        finalize_scan(frm, "", 'custom_scan_barcodes_for_free_items');
                        return;
                    }

                    frappe.db.get_value('Item', itemCode, 'item_name', function (r) {
                        const itemName = r.item_name;

                        if (existingFreeRow) {
                            console.log('✅ UPDATING EXISTING FREE ROW');

                            const currentQty = existingFreeRow.qty || 0;
                            const newQty = currentQty + 1;

                            frappe.model.set_value(existingFreeRow.doctype, existingFreeRow.name, {
                                'qty': newQty,
                                'custom_out_qty': newQty,
                                'barcode': barcode,
                                'rate': 0,
                                'amount': 0
                            });

                            if (!existingFreeRow.against_sales_order) {
                                frappe.model.set_value(existingFreeRow.doctype, existingFreeRow.name, 'against_sales_order', salesOrder);
                            }
                            set_so_detail(frm, existingFreeRow, itemCode, null, true);

                            finalize_free_scan(frm, `Updated free quantity to ${newQty} for ${itemName}`);

                        } else {
                            console.log('➕ CREATING NEW FREE ROW');

                            let newRow = frm.add_child('items', {
                                item_code: itemCode,
                                item_name: itemName,
                                qty: 1,
                                custom_out_qty: 1,
                                uom: uom,
                                conversion_factor: conversionRate,
                                batch_no: batchNo,
                                custom_expiry_date: expiryDate,
                                barcode: barcode,
                                is_free_item: 1,
                                rate: 0,
                                amount: 0,
                                against_sales_order: salesOrder
                            });

                            set_so_detail(frm, newRow, itemCode, null, true);
                            finalize_free_scan(frm, `Added 1 free ${uom} of ${itemName}`);
                        }
                    });
                });
            } else {
                frappe.msgprint(__("Barcode not found"));
                finalize_scan(frm, "", 'custom_scan_barcodes_for_free_items');
            }
        },
        error: function () {
            console.log('❌ FREE SCAN ERROR');
            finalize_scan(frm, "", 'custom_scan_barcodes_for_free_items');
        }
    });
}

// ===========================
// HELPER FUNCTIONS - ENHANCED WITH BETTER TIMING
// ===========================

function get_sales_order_reference(frm) {
    console.log('🔍 === SEARCHING FOR SALES ORDER REFERENCE ===');

    // Method 1: Check document field first
    if (frm.doc.sales_order) {
        console.log('📋 Found SO in doc.sales_order:', frm.doc.sales_order);
        return frm.doc.sales_order;
    }

    // Method 2: Check items table
    if (frm.doc.items && frm.doc.items.length > 0) {
        for (let item of frm.doc.items) {
            if (item.against_sales_order) {
                console.log('📋 Found SO in items:', item.against_sales_order);
                return item.against_sales_order;
            }
        }
    }

    // Method 3: Check URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const fromSO = urlParams.get('sales_order');
    if (fromSO) {
        console.log('📋 Found SO in URL:', fromSO);
        return fromSO;
    }

    // Method 4: Check route history
    if (frappe.route_history && frappe.route_history.length > 1) {
        const previousRoute = frappe.route_history[frappe.route_history.length - 2];
        if (previousRoute && previousRoute[1] === 'Sales Order') {
            const soName = previousRoute[2];
            console.log('📋 Found SO in route history:', soName);
            return soName;
        }
    }

    // Method 5: Check frappe.route_options
    if (frappe.route_options && frappe.route_options.sales_order) {
        console.log('📋 Found SO in route_options:', frappe.route_options.sales_order);
        return frappe.route_options.sales_order;
    }

    console.log('❌ No Sales Order reference found after all methods');
    return null;
}

function check_and_toggle_free_scanner(frm) {
    console.log('🔍 === CHECKING FREE SCANNER VISIBILITY ===');

    const salesOrder = get_sales_order_reference(frm);
    console.log('📋 Sales Order found:', salesOrder);

    if (!salesOrder) {
        console.log('❌ No Sales Order, hiding free scanner');
        hide_free_scanner(frm);
        return;
    }

    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Sales Order",
            name: salesOrder
        },
        callback: function (response) {
            if (response.message && response.message.items) {
                const freeItems = response.message.items.filter(item => {
                    const standardFree = item.is_free_item === 1 || item.is_free_item === "1" || item.is_free_item === true;
                    const customFree = item.custom_is_free_item === 1 || item.custom_is_free_item === "1" || item.custom_is_free_item === true;
                    return standardFree || customFree;
                });

                console.log('🎁 TOTAL FREE ITEMS FOUND:', freeItems.length);

                if (freeItems.length > 0) {
                    console.log('✅ FREE ITEMS EXIST - SHOWING SCANNER');
                    show_free_scanner(frm, freeItems.length);
                } else {
                    console.log('❌ NO FREE ITEMS - HIDING SCANNER');
                    hide_free_scanner(frm);
                }
            } else {
                console.log('❌ No Sales Order data or items found');
                hide_free_scanner(frm);
            }
        },
        error: function (err) {
            console.log('❌ Error fetching Sales Order:', err);
            hide_free_scanner(frm);
        }
    });
}

function show_free_scanner(frm, freeItemsCount) {
    console.log('🎁 SHOWING FREE SCANNER with', freeItemsCount, 'free items');
    frm.set_df_property('custom_scan_barcodes_for_free_items', 'hidden', 0);
    frm.toggle_display('custom_scan_barcodes_for_free_items', true);
    frm.set_df_property('custom_scan_barcodes_for_free_items', 'description',
        `🎁 Free Item Scanner (${freeItemsCount} free items available)`);
    frm.refresh_field('custom_scan_barcodes_for_free_items');
}

function hide_free_scanner(frm) {
    console.log('❌ HIDING FREE SCANNER');
    frm.toggle_display('custom_scan_barcodes_for_free_items', false);
    frm.set_df_property('custom_scan_barcodes_for_free_items', 'hidden', 1);
}

function auto_add_free_items_from_so(frm) {
    const salesOrder = get_sales_order_reference(frm);
    if (!salesOrder || !frm.is_new()) {
        return;
    }

    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Sales Order",
            name: salesOrder
        },
        callback: function (response) {
            if (response.message && response.message.items) {
                const freeItems = response.message.items.filter(item =>
                    item.is_free_item === 1 || item.custom_is_free_item === 1
                );

                freeItems.forEach(soItem => {
                    const existingItem = frm.doc.items.find(dnItem =>
                        dnItem.item_code === soItem.item_code &&
                        dnItem.is_free_item === 1
                    );

                    if (!existingItem && soItem.qty > 0) {
                        let newRow = frm.add_child('items', {
                            item_code: soItem.item_code,
                            item_name: soItem.item_name,
                            qty: 0,
                            custom_out_qty: 0,
                            uom: soItem.uom,
                            conversion_factor: soItem.conversion_factor || 1,
                            is_free_item: 1,
                            rate: 0,
                            amount: 0,
                            against_sales_order: salesOrder,
                            so_detail: soItem.name
                        });
                    }
                });

                if (freeItems.length > 0) {
                    frm.refresh_field('items');
                }
            }
        }
    });
}

function check_if_item_is_free_in_sales_order(frm, itemCode, callback) {
    const salesOrder = get_sales_order_reference(frm);

    if (!salesOrder) {
        callback(false, 0);
        return;
    }

    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Sales Order",
            name: salesOrder
        },
        callback: function (response) {
            if (response.message && response.message.items) {
                const freeItem = response.message.items.find(item =>
                    item.item_code === itemCode &&
                    (item.is_free_item === 1 || item.is_free_item === "1" || item.is_free_item === true ||
                        item.custom_is_free_item === 1 || item.custom_is_free_item === "1" || item.custom_is_free_item === true)
                );

                callback(!!freeItem, freeItem ? freeItem.qty : 0);
            } else {
                callback(false, 0);
            }
        }
    });
}

function set_so_detail(frm, row, itemCode, so_detail_id, is_free_item) {
    const salesOrder = get_sales_order_reference(frm);
    if (!salesOrder) {
        console.log('❌ No Sales Order for SO detail setting');
        return;
    }

    console.log('🔗 Setting SO detail:', {
        item: itemCode,
        so_detail_id: so_detail_id,
        is_free: is_free_item,
        row_name: row.name
    });

    if (so_detail_id) {
        frappe.model.set_value(row.doctype, row.name, 'so_detail', so_detail_id);
        console.log('✅ Set SO detail from barcode response:', so_detail_id);
    } else {
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Sales Order",
                name: salesOrder
            },
            callback: function (response) {
                if (response.message && response.message.items) {
                    let soItem;

                    if (is_free_item) {
                        soItem = response.message.items.find(item =>
                            item.item_code === itemCode &&
                            (item.is_free_item === 1 || item.custom_is_free_item === 1)
                        );
                    } else {
                        soItem = response.message.items.find(item =>
                            item.item_code === itemCode &&
                            !item.is_free_item && !item.custom_is_free_item
                        );
                    }

                    if (soItem) {
                        frappe.model.set_value(row.doctype, row.name, 'so_detail', soItem.name);
                        console.log('✅ Found and set SO detail:', soItem.name);
                    } else {
                        console.log('⚠️ No matching SO item found for:', itemCode);
                    }
                } else {
                    console.log('❌ Could not fetch SO details');
                }
            }
        });
    }
}

// ENHANCED: Delayed clear with better timing for USB scanners
function clear_barcode_field(frm, field_name) {
    // NEW: Don't clear immediately, add delay for USB scanners
    setTimeout(() => {
        frm.set_value(field_name, '');
        console.log('🧹 Cleared barcode field:', field_name);
    }, 1000); // 1 second delay to ensure scan completion
}

// ENHANCED: Better finalize with proper timing
function finalize_scan(frm, message, field_name) {
    console.log('🏁 FINALIZING SCAN');

    // Clear barcode field with delay
    clear_barcode_field(frm, field_name);

    // Refresh items table
    frm.refresh_field('items');

    // Calculate totals
    frm.script_manager.trigger("calculate_taxes_and_totals");

    if (message) {
        frappe.show_alert({
            message: __(message),
            indicator: 'green'
        });
    }

    // Reset scanning state and process queue with proper timing
    setTimeout(() => {
        frm._scanning = false;
        process_scan_queue(frm);
    }, 500); // Increased delay for USB scanner stability
}

function finalize_free_scan(frm, message) {
    console.log('🏁 FINALIZING FREE SCAN');

    clear_barcode_field(frm, 'custom_scan_barcodes_for_free_items');

    // Ensure all free items stay at rate 0
    frm.doc.items.forEach(item => {
        if (item.is_free_item === 1) {
            frappe.model.set_value(item.doctype, item.name, 'rate', 0);
            frappe.model.set_value(item.doctype, item.name, 'amount', 0);
        }
    });

    frm.refresh_field('items');
    frm.script_manager.trigger("calculate_taxes_and_totals");

    if (message) {
        frappe.show_alert({
            message: __(message),
            indicator: 'blue'
        });
    }

    // Reset scanning state and process queue
    setTimeout(() => {
        frm._scanning = false;
        process_scan_queue(frm);
    }, 500);
}

// ENHANCED: Process queued scans with better timing
function process_scan_queue(frm) {
    if (!frm._scan_queue || frm._scan_queue.length === 0) {
        return;
    }

    console.log('📦 Processing scan queue, items:', frm._scan_queue.length);

    const nextScan = frm._scan_queue.shift();

    // Add small delay between queued scans
    setTimeout(() => {
        if (nextScan.type === 'regular') {
            frm.set_value('custom_scan_barcodes', nextScan.barcode);
        } else if (nextScan.type === 'free') {
            frm.set_value('custom_scan_barcodes_for_free_items', nextScan.barcode);
        }
    }, 100);
}

// ===========================
// DELIVERY NOTE ITEM EVENTS - SAME AS BEFORE
// ===========================

frappe.ui.form.on('Delivery Note Item', {
    custom_out_qty: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        // FIXED: Add check to prevent circular triggers
        if (row._updating_qty) return;
        row._updating_qty = true;

        console.log('🔄 custom_out_qty triggered:', row.custom_out_qty, 'current qty:', row.qty);

        if (row.custom_out_qty !== row.qty) {
            frappe.model.set_value(cdt, cdn, 'qty', row.custom_out_qty || 0);
        }

        if (row.is_free_item === 1) {
            frappe.model.set_value(cdt, cdn, 'rate', 0);
            frappe.model.set_value(cdt, cdn, 'amount', 0);
        }

        // FIXED: Reset flag after short delay
        setTimeout(() => {
            row._updating_qty = false;
        }, 100);
    },

    qty: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        // FIXED: Add check to prevent circular triggers
        if (row._updating_qty) return;
        row._updating_qty = true;

        console.log('🔄 qty triggered:', row.qty, 'current custom_out_qty:', row.custom_out_qty);

        if (row.is_free_item === 1) {
            frappe.model.set_value(cdt, cdn, 'rate', 0);
            frappe.model.set_value(cdt, cdn, 'amount', 0);
        }

        if (row.qty !== row.custom_out_qty) {
            frappe.model.set_value(cdt, cdn, 'custom_out_qty', row.qty || 0);
        }

        // FIXED: Reset flag after short delay
        setTimeout(() => {
            row._updating_qty = false;
        }, 100);
    },

    rate: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        if (row.is_free_item === 1 && row.rate !== 0) {
            frappe.model.set_value(cdt, cdn, 'rate', 0);
            frappe.model.set_value(cdt, cdn, 'amount', 0);
        }
    },

    item_code: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        if (row.is_free_item === 1) {
            frappe.model.set_value(cdt, cdn, 'rate', 0);
            frappe.model.set_value(cdt, cdn, 'amount', 0);
        }

        if (row.qty && !row.custom_out_qty) {
            frappe.model.set_value(cdt, cdn, 'custom_out_qty', row.qty);
        }
    }
});