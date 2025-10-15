// //ده كود في ملفات المشروع هيفضل في ملفات المشروع
// frappe.ui.form.on('Purchase Receipt', {
//     scan_barcode: function (frm) {
//         if (!frm.doc.scan_barcode) return;

//         const barcode = frm.doc.scan_barcode;
//         const qty = 1; // Default to 1 per scan

//         frappe.call({
//             method: 'dmc.barcode_details.get_barcode_details',
//             args: { barcode },
//             async: false,
//             callback: function (response) {
//                 if (response.message) {
//                     const uom = response.message.barcode_uom[0]['uom'];
//                     const batchNo = response.message.batch_id;
//                     const itemCode = response.message.item_code[0]['parent'];
//                     const expiryDate = response.message.formatted_date;
//                     const conversionRate = response.message.conversion_factor[0]['conversion_factor'];

//                     frappe.db.get_value('Item', itemCode, 'item_name', function (r) {
//                         const itemName = r.item_name;

//                         // Check if item with same item_code and batch already exists
//                         let existingRow = null;
//                         if (frm.doc.items && frm.doc.items.length > 0) {
//                             // Debug: Log what we're looking for
//                             console.log('Looking for:', { itemCode, batchNo, uom });
//                             console.log('Existing items:', frm.doc.items.map(i => ({
//                                 item_code: i.item_code,
//                                 batch_no: i.batch_no,
//                                 uom: i.uom
//                             })));

//                             existingRow = frm.doc.items.find(item =>
//                                 String(item.item_code).trim() === String(itemCode).trim() &&
//                                 String(item.batch_no).trim() === String(batchNo).trim() &&
//                                 String(item.uom).trim() === String(uom).trim()
//                             );

//                             console.log('Found existing row:', existingRow ? 'YES' : 'NO');
//                         }

//                         if (existingRow) {
//                             // Update existing row quantity
//                             let newQty = flt(existingRow.qty) + qty;
//                             frappe.model.set_value(existingRow.doctype, existingRow.name, 'qty', newQty);
//                             frappe.model.set_value(existingRow.doctype, existingRow.name, 'received_stock_qty', newQty * conversionRate);
//                             frappe.model.set_value(existingRow.doctype, existingRow.name, 'stock_qty', newQty * conversionRate);

//                             frm.refresh_field('items');
//                             frm.trigger('calculate_taxes_and_totals');

//                             // Update total quantities
//                             let total_qty = 0;
//                             frm.doc.items.forEach(function (item) {
//                                 total_qty += flt(item.qty);
//                             });
//                             frm.set_value('total_qty', total_qty);

//                             frappe.show_alert({
//                                 message: __(`Updated to ${newQty} ${uom} of ${itemName}`),
//                                 indicator: 'blue'
//                             });
//                         } else {
//                             // Add new row if not exists
//                             let newRow = frm.add_child('items', {
//                                 item_code: itemCode,
//                                 item_name: itemName,
//                                 qty: qty,
//                                 uom: uom,
//                                 conversion_factor: conversionRate,
//                                 batch_no: batchNo,
//                                 custom_expiry_date: expiryDate,
//                                 barcode: barcode,
//                                 received_stock_qty: qty * conversionRate,
//                                 stock_qty: qty * conversionRate
//                             });

//                             // Set warehouse from PO if available, else use default warehouse
//                             if (frm.doc.custom_purchase_order_name) {
//                                 frappe.db.get_doc('Purchase Order', frm.doc.custom_purchase_order_name).then(po => {
//                                     if (po && po.items) {
//                                         let po_item = po.items.find(i => i.item_code === itemCode);
//                                         if (po_item && po_item.warehouse) {
//                                             frappe.model.set_value(newRow.doctype, newRow.name, 'warehouse', po_item.warehouse);
//                                         }
//                                     }
//                                 });
//                             } else if (frm.doc.set_warehouse) {
//                                 frappe.model.set_value(newRow.doctype, newRow.name, 'warehouse', frm.doc.set_warehouse);
//                             }

//                             // Refresh the field first
//                             frm.refresh_field('items');

//                             // Trigger item code change to fetch price list rate
//                             frm.script_manager.trigger('item_code', newRow.doctype, newRow.name);

//                             // Alternative method to fetch price list rate if above doesn't work
//                             setTimeout(() => {
//                                 frappe.model.set_value(newRow.doctype, newRow.name, 'item_code', itemCode);
//                                 frm.refresh_field('items');

//                                 // Calculate totals
//                                 frm.trigger('calculate_taxes_and_totals');

//                                 // Update total quantities
//                                 let total_qty = 0;
//                                 frm.doc.items.forEach(function (item) {
//                                     total_qty += flt(item.qty);
//                                 });
//                                 frm.set_value('total_qty', total_qty);

//                             }, 100);

//                             frappe.show_alert({
//                                 message: __(`Added ${qty} ${uom} of ${itemName}`),
//                                 indicator: 'green'
//                             });
//                         }

//                         // Clear the barcode field
//                         frm.set_value('scan_barcode', '');
//                     });
//                 }
//             }
//         });
//     },

//     items_add: function (frm, cdt, cdn) {
//         let row = locals[cdt][cdn];
//         if (frm.doc.custom_purchase_order_name) {
//             frappe.model.set_value(cdt, cdn, 'purchase_order', frm.doc.custom_purchase_order_name);
//         }
//     },

//     refresh: function (frm) {
//         if (frm.doc.__is_refreshing) return;
//         frm.doc.__is_refreshing = true;

//         frm.doc.item_map = {};

//         setTimeout(() => {
//             if (frm.doc.items && frm.doc.items.length > 0 && frm.doc.items[0].barcode) {
//                 frm.doc.items.forEach(row => {
//                     if (row.barcode) {
//                         frm.doc.item_map[row.barcode] = {
//                             uom: row.uom,
//                             itemCode: row.item_code,
//                             batchNo: row.batch_no
//                         };
//                     }
//                 });
//             }
//             frm.doc.__is_refreshing = false;
//         }, 200);

//         if (frm.doc.docstatus === 1) {
//             frm.set_read_only();
//         }
//     },

//     onload: function (frm) {
//         if (frm.doc.custom_purchase_invoice_name) {
//             frappe.db.get_doc('Purchase Invoice', frm.doc.custom_purchase_invoice_name).then(pinv => {
//                 if (pinv && pinv.custom_is_landed_cost) {
//                     frm.set_value('custom_shipment_order_name', pinv.custom_shipment_name_ref || '');
//                 }
//             });
//         }
//     },
// });

// ده الكود الجديد اللي يروح في ملفات المشروع
// يحل محل الكود القديم بتاع scan_barcode

// frappe.ui.form.on('Purchase Receipt', {
//     scan_barcode: function (frm) {
//         if (!frm.doc.scan_barcode) return;

//         const barcode = frm.doc.scan_barcode;

//         frappe.call({
//             method: 'dmc.barcode_details.get_barcode_details',
//             args: { barcode },
//             async: false,
//             callback: function (response) {
//                 if (response.message) {
//                     const uom = response.message.barcode_uom[0]['uom'];
//                     const batchNo = response.message.batch_id;
//                     const itemCode = response.message.item_code[0]['parent'];
//                     const expiryDate = response.message.formatted_date;
//                     const conversionRate = response.message.conversion_factor[0]['conversion_factor'];

//                     frappe.db.get_value('Item', itemCode, 'item_name', function (r) {
//                         const itemName = r.item_name;

//                         // ========================================
//                         // NEW LOGIC: Add to scanned_items table
//                         // ========================================

//                         // Check if item exists in scanned_items with same item_code, batch, and UOM
//                         let existingScannedRow = null;
//                         if (frm.doc.custom_scanned_items && frm.doc.custom_scanned_items.length > 0) {
//                             existingScannedRow = frm.doc.custom_scanned_items.find(item =>
//                                 String(item.item_code).trim() === String(itemCode).trim() &&
//                                 String(item.batch_no).trim() === String(batchNo).trim() &&
//                                 String(item.uom).trim() === String(uom).trim()
//                             );
//                         }

//                         if (existingScannedRow) {
//                             // Update existing scanned row - increment received_qty
//                             let newReceivedQty = flt(existingScannedRow.received_qty) + 1;
//                             let newReceivedStockQty = newReceivedQty * conversionRate;

//                             frappe.model.set_value(
//                                 existingScannedRow.doctype,
//                                 existingScannedRow.name,
//                                 'received_qty',
//                                 newReceivedQty
//                             );
//                             frappe.model.set_value(
//                                 existingScannedRow.doctype,
//                                 existingScannedRow.name,
//                                 'received_stock_qty',
//                                 newReceivedStockQty
//                             );
//                             frappe.model.set_value(
//                                 existingScannedRow.doctype,
//                                 existingScannedRow.name,
//                                 'stock_qty',
//                                 newReceivedStockQty
//                             );

//                             frappe.show_alert({
//                                 message: __(`✅ Updated: ${itemName} - ${newReceivedQty} ${uom}`),
//                                 indicator: 'blue'
//                             });
//                         } else {
//                             // Add new row to scanned_items
//                             let newScannedRow = frm.add_child('custom_scanned_items', {
//                                 item_code: itemCode,
//                                 item_name: itemName,
//                                 batch_no: batchNo,
//                                 uom: uom,
//                                 conversion_factor: conversionRate,
//                                 received_qty: 1,
//                                 received_stock_qty: 1 * conversionRate,
//                                 stock_qty: 1 * conversionRate,
//                                 barcode: barcode
//                             });

//                             frappe.show_alert({
//                                 message: __(`✅ Added to scanned items: ${itemName} - 1 ${uom}`),
//                                 indicator: 'green'
//                             });
//                         }

//                         frm.refresh_field('custom_scanned_items');

//                         // ========================================
//                         // AGGREGATE AND UPDATE ITEMS TABLE
//                         // ========================================
//                         const aggregationSuccess = aggregate_scanned_to_items(frm);

//                         // If aggregation failed due to qty exceeded, remove the last scan
//                         if (aggregationSuccess === false) {
//                             console.log('❌ Aggregation failed - removing last scanned item');

//                             // Remove the item we just added/updated
//                             if (existingScannedRow) {
//                                 // Revert the quantity update
//                                 let prevQty = flt(existingScannedRow.received_qty) - 1;
//                                 frappe.model.set_value(
//                                     existingScannedRow.doctype,
//                                     existingScannedRow.name,
//                                     'received_qty',
//                                     prevQty
//                                 );
//                                 frappe.model.set_value(
//                                     existingScannedRow.doctype,
//                                     existingScannedRow.name,
//                                     'received_stock_qty',
//                                     prevQty * conversionRate
//                                 );
//                                 frappe.model.set_value(
//                                     existingScannedRow.doctype,
//                                     existingScannedRow.name,
//                                     'stock_qty',
//                                     prevQty * conversionRate
//                                 );
//                             } else {
//                                 // Remove the newly added row
//                                 const lastRow = frm.doc.custom_scanned_items[frm.doc.custom_scanned_items.length - 1];
//                                 frappe.model.clear_doc(lastRow.doctype, lastRow.name);
//                             }

//                             frm.refresh_field('custom_scanned_items');

//                             // Don't clear barcode - let user see the error
//                             return;
//                         }

//                         // Clear the barcode field
//                         frm.set_value('scan_barcode', '');
//                     });
//                 }
//             }
//         });
//     },

//     items_add: function (frm, cdt, cdn) {
//         let row = locals[cdt][cdn];
//         if (frm.doc.custom_purchase_order_name) {
//             frappe.model.set_value(cdt, cdn, 'purchase_order', frm.doc.custom_purchase_order_name);
//         }
//     },

//     refresh: function (frm) {
//         if (frm.doc.__is_refreshing) return;
//         frm.doc.__is_refreshing = true;

//         frm.doc.item_map = {};

//         setTimeout(() => {
//             if (frm.doc.items && frm.doc.items.length > 0 && frm.doc.items[0].barcode) {
//                 frm.doc.items.forEach(row => {
//                     if (row.barcode) {
//                         frm.doc.item_map[row.barcode] = {
//                             uom: row.uom,
//                             itemCode: row.item_code,
//                             batchNo: row.batch_no
//                         };
//                     }
//                 });
//             }
//             frm.doc.__is_refreshing = false;
//         }, 200);

//         if (frm.doc.docstatus === 1) {
//             frm.set_read_only();
//         }
//     },

//     onload: function (frm) {
//         if (frm.doc.custom_purchase_invoice_name) {
//             frappe.db.get_doc('Purchase Invoice', frm.doc.custom_purchase_invoice_name).then(pinv => {
//                 if (pinv && pinv.custom_is_landed_cost) {
//                     frm.set_value('custom_shipment_order_name', pinv.custom_shipment_name_ref || '');
//                 }
//             });
//         }
//     },
// });

// // ========================================
// // AGGREGATION FUNCTION WITH VALIDATION
// // ========================================
// function aggregate_scanned_to_items(frm) {
//     console.log('🔄 Aggregating scanned items to main items table...');

//     if (!frm.doc.custom_scanned_items || frm.doc.custom_scanned_items.length === 0) {
//         console.log('⚠️ No scanned items to aggregate');
//         return;
//     }

//     if (!frm.doc.items || frm.doc.items.length === 0) {
//         console.log('⚠️ No items in main table');
//         return;
//     }

//     // Create aggregation map: key = item_code + batch_no
//     const aggregateMap = {};

//     frm.doc.custom_scanned_items.forEach(scannedItem => {
//         const key = `${scannedItem.item_code}_${scannedItem.batch_no}`;

//         if (!aggregateMap[key]) {
//             aggregateMap[key] = {
//                 item_code: scannedItem.item_code,
//                 batch_no: scannedItem.batch_no,
//                 total_received_stock_qty: 0
//             };
//         }

//         aggregateMap[key].total_received_stock_qty += flt(scannedItem.received_stock_qty);
//     });

//     console.log('📊 Aggregation Map:', aggregateMap);

//     // Update main items table with VALIDATION
//     let validationFailed = false;

//     frm.doc.items.forEach(item => {
//         if (validationFailed) return; // Skip if already failed

//         const key = `${item.item_code}_${item.batch_no}`;

//         if (aggregateMap[key]) {
//             const aggregatedReceivedQty = aggregateMap[key].total_received_stock_qty;

//             // Get accepted qty (stock_qty from PI - this is the max allowed)
//             const acceptedStockQty = flt(item.stock_qty); // This should be from PI

//             console.log(`✅ Updating item ${item.item_code} batch ${item.batch_no}:`);
//             console.log(`   Accepted Stock Qty (from PI): ${acceptedStockQty}`);
//             console.log(`   Current received_stock_qty: ${item.received_stock_qty}`);
//             console.log(`   New aggregated received qty: ${aggregatedReceivedQty}`);

//             // ========================================
//             // VALIDATION: Received Qty <= Accepted Qty
//             // ========================================
//             if (aggregatedReceivedQty > acceptedStockQty) {
//                 console.log(`❌ VALIDATION FAILED: Received (${aggregatedReceivedQty}) > Accepted (${acceptedStockQty})`);

//                 frappe.msgprint({
//                     title: __('Quantity Exceeded'),
//                     message: __(`Item: <b>${item.item_name}</b><br>Batch: <b>${item.batch_no}</b><br><br>Received Qty: <b>${aggregatedReceivedQty} units</b><br>Accepted Qty: <b>${acceptedStockQty} units</b><br><br>❌ You cannot receive more than the accepted quantity!<br><br>The last scan will be rejected.`),
//                     indicator: 'red',
//                     primary_action: {
//                         label: __('OK'),
//                         action: function () {
//                             // Do nothing, just close
//                         }
//                     }
//                 });

//                 frappe.utils.play_sound("error");

//                 // Return false to indicate failure
//                 return false;
//             }

//             // Update received_stock_qty (NOT qty - qty stays as accepted)
//             frappe.model.set_value(item.doctype, item.name, 'received_stock_qty', aggregatedReceivedQty);

//             // Calculate received_qty in UOM
//             if (item.conversion_factor && item.conversion_factor > 0) {
//                 const receivedQtyInUOM = aggregatedReceivedQty / item.conversion_factor;
//                 frappe.model.set_value(item.doctype, item.name, 'received_qty', receivedQtyInUOM);
//             }

//             // Show progress
//             const percentage = (aggregatedReceivedQty / acceptedStockQty * 100).toFixed(1);
//             frappe.show_alert({
//                 message: __(`📦 ${item.item_name}: ${aggregatedReceivedQty}/${acceptedStockQty} units (${percentage}%)`),
//                 indicator: aggregatedReceivedQty === acceptedStockQty ? 'green' : 'blue'
//             }, 3);
//         }
//     });

//     frm.refresh_field('items');

//     // Recalculate totals
//     frm.trigger('calculate_taxes_and_totals');

//     console.log('✅ Aggregation completed successfully');
//     return true; // Return true to indicate success
// }


// ========================================
// MAIN PURCHASE RECEIPT SCRIPT - WITH FULL VALIDATION
// ========================================

let aggregateTimeout = null;
let refreshTimeout = null;

frappe.ui.form.on('Purchase Receipt', {
    scan_barcode: function (frm) {
        if (!frm.doc.scan_barcode) return;

        const barcode = frm.doc.scan_barcode;

        frappe.call({
            method: 'dmc.barcode_details.get_barcode_details',
            args: { barcode },
            callback: function (response) {
                if (!response.message) {
                    frappe.msgprint(__("Invalid barcode. Could not fetch details."));
                    frm.set_value('scan_barcode', '');
                    return;
                }

                const uom = response.message.barcode_uom[0]['uom'];
                const batchNo = response.message.batch_id;
                const itemCode = response.message.item_code[0]['parent'];
                const expiryDate = response.message.formatted_date;
                const conversionRate = response.message.conversion_factor[0]['conversion_factor'];

                let purchaseInvoice = get_purchase_invoice_reference(frm);

                if (!purchaseInvoice) {
                    process_scanned_item(frm, {
                        barcode, batchNo, itemCode, uom, conversionRate, expiryDate
                    });
                    return;
                }

                // Use cache for PI
                if (!frm._pi_items || frm._pi_name !== purchaseInvoice) {
                    frappe.call({
                        method: "frappe.client.get",
                        args: {
                            doctype: "Purchase Invoice",
                            name: purchaseInvoice
                        },
                        callback: function (piResponse) {
                            if (!piResponse.message || !piResponse.message.items) {
                                frappe.msgprint(__("Could not fetch Purchase Invoice details."));
                                frm.set_value('scan_barcode', '');
                                return;
                            }

                            frm._pi_items = piResponse.message.items;
                            frm._pi_name = purchaseInvoice;

                            const matchedPIItem = frm._pi_items.find(item =>
                                item.batch_no === batchNo && item.item_code === itemCode
                            );

                            if (!matchedPIItem) {
                                frappe.msgprint({
                                    title: __('Invalid Batch Number'),
                                    message: __(`Scanned Batch No <b>${batchNo}</b> is not in Purchase Invoice <b>${purchaseInvoice}</b>.<br><br>❌ Please scan a valid batch from the Purchase Invoice.`),
                                    indicator: 'red'
                                });
                                frm.set_value('scan_barcode', '');
                                return;
                            }

                            process_scanned_item(frm, {
                                barcode, batchNo, itemCode, uom, conversionRate, expiryDate
                            });
                        }
                    });
                } else {
                    const matchedPIItem = frm._pi_items.find(item =>
                        item.batch_no === batchNo && item.item_code === itemCode
                    );

                    if (!matchedPIItem) {
                        frappe.msgprint({
                            title: __('Invalid Batch Number'),
                            message: __(`Scanned Batch No <b>${batchNo}</b> is not in Purchase Invoice <b>${purchaseInvoice}</b>.<br><br>❌ Please scan a valid batch from the Purchase Invoice.`),
                            indicator: 'red'
                        });
                        frm.set_value('scan_barcode', '');
                        return;
                    }

                    process_scanned_item(frm, {
                        barcode, batchNo, itemCode, uom, conversionRate, expiryDate
                    });
                }
            }
        });
    },

    items_add: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (frm.doc.custom_purchase_order_name) {
            frappe.model.set_value(cdt, cdn, 'purchase_order', frm.doc.custom_purchase_order_name);
        }

        const purchaseInvoice = get_purchase_invoice_reference(frm);
        if (purchaseInvoice) {
            if (row.item_code) {
                setTimeout(() => validate_item_against_pi(frm, cdt, cdn), 300);
            }
            if (row.batch_no) {
                setTimeout(() => validate_batch_on_change(frm, cdt, cdn), 500);
            }
        }
    },

    refresh: function (frm) {
        if (frm.doc.docstatus === 1) {
            frm.set_read_only();
        }
        store_purchase_invoice_reference(frm);

        // Clear PI cache
        frm._pi_items = null;
        frm._pi_name = null;
    },

    onload: function (frm) {
        if (frm.doc.custom_purchase_invoice_name) {
            frappe.db.get_doc('Purchase Invoice', frm.doc.custom_purchase_invoice_name).then(pinv => {
                if (pinv && pinv.custom_is_landed_cost) {
                    frm.set_value('custom_shipment_order_name', pinv.custom_shipment_name_ref || '');
                }
            });
        }
        store_purchase_invoice_reference(frm);
    },

    custom_purchase_invoice_name: function (frm) {
        store_purchase_invoice_reference(frm);
        frm._pi_items = null;
        frm._pi_name = null;
    },

    validate: function (frm) {
        return validate_purchase_receipt(frm);
    },

    before_save: function (frm) {
        return validate_purchase_receipt(frm);
    }
});

function get_purchase_invoice_reference(frm) {
    let purchaseInvoice =
        frm.doc.custom_purchase_invoice_name ||
        frm.doc.custom_purchase_invoice ||
        (frm.doc.items && frm.doc.items.length > 0 ?
            frm.doc.items.find(item => item.purchase_invoice)?.purchase_invoice : null) ||
        frm._stored_purchase_invoice;

    return purchaseInvoice;
}

function store_purchase_invoice_reference(frm) {
    let purchaseInvoice =
        frm.doc.custom_purchase_invoice_name ||
        frm.doc.custom_purchase_invoice ||
        (frm.doc.items && frm.doc.items.length > 0 ?
            frm.doc.items.find(item => item.purchase_invoice)?.purchase_invoice : null);

    if (purchaseInvoice) {
        frm._stored_purchase_invoice = purchaseInvoice;
        if (!frm.doc.custom_purchase_invoice_name) {
            frm.set_value('custom_purchase_invoice_name', purchaseInvoice);
        }
    }
}

function process_scanned_item(frm, itemData) {
    const { barcode, batchNo, itemCode, uom, conversionRate, expiryDate } = itemData;

    frappe.db.get_value('Item', itemCode, 'item_name', function (r) {
        const itemName = r.item_name;

        let existingScannedRow = null;
        if (frm.doc.custom_scanned_items && frm.doc.custom_scanned_items.length > 0) {
            existingScannedRow = frm.doc.custom_scanned_items.find(item =>
                String(item.item_code).trim() === String(itemCode).trim() &&
                String(item.batch_no).trim() === String(batchNo).trim() &&
                String(item.uom).trim() === String(uom).trim()
            );
        }

        if (existingScannedRow) {
            let newReceivedQty = flt(existingScannedRow.received_qty) + 1;
            let newReceivedStockQty = newReceivedQty * conversionRate;

            existingScannedRow.received_qty = newReceivedQty;
            existingScannedRow.received_stock_qty = newReceivedStockQty;
            existingScannedRow.stock_qty = newReceivedStockQty;
        } else {
            frm.add_child('custom_scanned_items', {
                item_code: itemCode,
                item_name: itemName,
                batch_no: batchNo,
                uom: uom,
                conversion_factor: conversionRate,
                received_qty: 1,
                received_stock_qty: 1 * conversionRate,
                stock_qty: 1 * conversionRate,
                barcode: barcode
            });
        }

        frm.set_value('scan_barcode', '');

        debounced_aggregate_and_refresh(frm);
    });
}

function debounced_aggregate_and_refresh(frm) {
    if (aggregateTimeout) clearTimeout(aggregateTimeout);

    aggregateTimeout = setTimeout(() => {
        aggregate_scanned_to_items(frm);

        if (refreshTimeout) clearTimeout(refreshTimeout);
        refreshTimeout = setTimeout(() => {
            frm.refresh_field('custom_scanned_items');
            frm.refresh_field('items');
        }, 100);
    }, 400);
}

function aggregate_scanned_to_items(frm) {
    if (!frm.doc.custom_scanned_items || frm.doc.custom_scanned_items.length === 0) {
        return;
    }

    if (!frm.doc.items || frm.doc.items.length === 0) {
        return;
    }

    const aggregateMap = {};

    frm.doc.custom_scanned_items.forEach(scannedItem => {
        const key = `${scannedItem.item_code}_${scannedItem.batch_no}`;

        if (!aggregateMap[key]) {
            aggregateMap[key] = {
                item_code: scannedItem.item_code,
                batch_no: scannedItem.batch_no,
                total_received_stock_qty: 0
            };
        }

        aggregateMap[key].total_received_stock_qty += flt(scannedItem.received_stock_qty);
    });

    frm.doc.items.forEach(item => {
        const key = `${item.item_code}_${item.batch_no}`;

        if (aggregateMap[key]) {
            const aggregatedReceivedQty = aggregateMap[key].total_received_stock_qty;

            item.received_stock_qty = aggregatedReceivedQty;

            if (item.conversion_factor && item.conversion_factor > 0) {
                item.received_qty = aggregatedReceivedQty / item.conversion_factor;
            }
        }
    });

    return true;
}

function validate_purchase_receipt(frm) {
    return new Promise((resolve, reject) => {
        let purchaseInvoice = get_purchase_invoice_reference(frm);

        if (!purchaseInvoice) {
            resolve();
            return;
        }

        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Purchase Invoice",
                name: purchaseInvoice
            },
            callback: function (response) {
                if (!response.message || !response.message.items) {
                    frappe.msgprint(__("Could not fetch Purchase Invoice details for validation."));
                    reject();
                    return;
                }

                const piItems = response.message.items;
                const piItemMap = {};
                const piBatchMap = {};

                piItems.forEach(item => {
                    const itemCode = item.item_code;
                    const batchNo = item.batch_no;

                    if (!piItemMap[itemCode]) {
                        piItemMap[itemCode] = { batches: [] };
                    }

                    if (batchNo) {
                        piItemMap[itemCode].batches.push(batchNo);
                        piBatchMap[batchNo] = itemCode;
                    }
                });

                let validationErrors = [];

                if (!frm.doc.items || frm.doc.items.length === 0) {
                    frappe.msgprint({
                        title: __('No Items'),
                        message: __(`Purchase Receipt has no items.`),
                        indicator: 'red'
                    });
                    reject();
                    return;
                }

                for (let i = 0; i < frm.doc.items.length; i++) {
                    const item = frm.doc.items[i];
                    const itemCode = item.item_code;
                    const batchNo = item.batch_no;

                    if (!piItemMap[itemCode]) {
                        validationErrors.push(`Row ${i + 1}: Item ${itemCode} is not in Purchase Invoice`);
                        continue;
                    }

                    if (batchNo && !piBatchMap[batchNo]) {
                        validationErrors.push(`Row ${i + 1}: Batch No ${batchNo} is not in Purchase Invoice`);
                    }
                }

                if (validationErrors.length > 0) {
                    frappe.msgprint({
                        title: __('Validation Failed'),
                        message: validationErrors.join('<br><br>'),
                        indicator: 'red'
                    });
                    reject();
                    return;
                }

                resolve();
            },
            error: function (err) {
                frappe.msgprint(__("Error fetching Purchase Invoice."));
                reject();
            }
        });
    });
}

function validate_item_against_pi(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const purchaseInvoice = get_purchase_invoice_reference(frm);

    if (!purchaseInvoice || !row.item_code) {
        return;
    }

    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Purchase Invoice",
            name: purchaseInvoice
        },
        callback: function (response) {
            if (!response.message || !response.message.items) return;

            const piItem = response.message.items.find(item => item.item_code === row.item_code);

            if (!piItem) {
                frappe.model.set_value(cdt, cdn, 'item_code', '');
                frappe.msgprint({
                    title: __('Invalid Item'),
                    message: __(`Item <b>${row.item_code}</b> is not in Purchase Invoice <b>${purchaseInvoice}</b>.`),
                    indicator: 'red'
                });
            }
        }
    });
}

function validate_batch_on_change(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    let purchaseInvoice = get_purchase_invoice_reference(frm);

    if (!purchaseInvoice || !row.batch_no || !row.item_code) {
        return;
    }

    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Purchase Invoice",
            name: purchaseInvoice
        },
        callback: function (response) {
            if (!response.message || !response.message.items) return;

            const validBatch = response.message.items.find(
                item => item.batch_no === row.batch_no && item.item_code === row.item_code
            );

            if (!validBatch) {
                const invalidBatch = row.batch_no;
                const invalidItem = row.item_code;

                frappe.model.clear_doc(cdt, cdn);
                frm.refresh_field('items');

                frappe.msgprint({
                    title: __('Invalid Batch Number'),
                    message: __(`Batch No <b>${invalidBatch}</b> is not valid for item <b>${invalidItem}</b> in Purchase Invoice <b>${purchaseInvoice}</b>.`),
                    indicator: 'red'
                });
            }
        }
    });
}

frappe.ui.form.on('Purchase Receipt Item', {
    item_code: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const purchaseInvoice = get_purchase_invoice_reference(frm);

        if (purchaseInvoice) {
            validate_item_against_pi(frm, cdt, cdn);
            if (row.batch_no) {
                validate_batch_on_change(frm, cdt, cdn);
            }
        }
    },

    batch_no: function (frm, cdt, cdn) {
        const purchaseInvoice = get_purchase_invoice_reference(frm);
        if (purchaseInvoice) {
            validate_batch_on_change(frm, cdt, cdn);
        }
    }
});

frappe.ui.form.on('Purchase Receipt Scanned Item', {
    received_qty: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        if (row.conversion_factor && row.conversion_factor > 0) {
            const newReceivedStockQty = flt(row.received_qty) * flt(row.conversion_factor);

            row.received_stock_qty = newReceivedStockQty;
            row.stock_qty = newReceivedStockQty;
        }

        debounced_aggregate_and_refresh(frm);
    },

    received_stock_qty: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        if (row.conversion_factor && row.conversion_factor > 0) {
            const newReceivedQty = flt(row.received_stock_qty) / flt(row.conversion_factor);

            row.received_qty = newReceivedQty;
            row.stock_qty = flt(row.received_stock_qty);
        }

        debounced_aggregate_and_refresh(frm);
    }
});