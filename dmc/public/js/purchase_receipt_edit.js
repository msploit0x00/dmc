frappe.ui.form.on('Purchase Receipt', {
    // received_stock_qty: function (frm) {
    //     update_total_qty(frm);
    //     console.log("✅ Custom Purchase Receipt Client Script loaded");
    // },


    // base_amount: function (frm) {
    //     update_total_amount(frm);
    //     console.log("✅ Custom Purchase Receipt Client Script loaded");
    // },

    // items_on_form_rendered: function (frm) {
    //     update_total_qty(frm);
    // },

    // scan_barcode: function (frm) {
    //     if (!frm.doc.scan_barcode) return;

    //     const barcode = frm.doc.scan_barcode;
    //     const qty = 1; // Default to 1 per scan; can be enhanced to prompt/input later

    //     frappe.call({
    //         method: 'dmc.barcode_details.get_barcode_details',
    //         args: { barcode },
    //         async: false,
    //         callback: function (response) {
    //             if (response.message) {
    //                 const uom = response.message.barcode_uom[0]['uom'];
    //                 const batchNo = response.message.batch_id;
    //                 const itemCode = response.message.item_code[0]['parent'];
    //                 const expiryDate = response.message.formatted_date;
    //                 const conversionRate = response.message.conversion_factor[0]['conversion_factor'];

    //                 frappe.db.get_value('Item', itemCode, 'item_name', function (r) {
    //                     const itemName = r.item_name;

    //                     // Always add a new row for each scan
    //                     let newRow = frm.add_child('items', {
    //                         item_code: itemCode,
    //                         item_name: itemName,
    //                         qty: qty,
    //                         uom: uom,
    //                         conversion_factor: conversionRate,
    //                         batch_no: batchNo,
    //                         custom_expiry_date: expiryDate,
    //                         barcode: barcode,
    //                         received_stock_qty: qty * conversionRate,
    //                         stock_qty: qty * conversionRate
    //                     });

    //                     // Set warehouse from PO if available, else use default warehouse
    //                     if (frm.doc.custom_purchase_order_name) {
    //                         frappe.db.get_doc('Purchase Order', frm.doc.custom_purchase_order_name).then(po => {
    //                             if (po && po.items) {
    //                                 let po_item = po.items.find(i => i.item_code === itemCode);
    //                                 if (po_item && po_item.warehouse) {
    //                                     frappe.model.set_value(newRow.doctype, newRow.name, 'warehouse', po_item.warehouse);
    //                                 }
    //                             }
    //                         });
    //                     } else if (frm.doc.set_warehouse) {
    //                         frappe.model.set_value(newRow.doctype, newRow.name, 'warehouse', frm.doc.set_warehouse);
    //                     }

    //                     // update_total_amount(frm);
    //                     // update_total_qty(frm);
    //                     frm.refresh_field('items');
    //                     frm.set_value('scan_barcode', '');
    //                     frappe.show_alert({
    //                         message: __(`Added ${qty} ${uom} of ${itemName}`),
    //                         indicator: 'green'
    //                     });
    //                 });
    //             }
    //         }
    //     });
    // },
    scan_barcode: function (frm) {
        if (!frm.doc.scan_barcode) return;

        const barcode = frm.doc.scan_barcode;
        const qty = 1; // Default to 1 per scan

        frappe.call({
            method: 'dmc.barcode_details.get_barcode_details',
            args: { barcode },
            async: false,
            callback: function (response) {
                if (response.message) {
                    const uom = response.message.barcode_uom[0]['uom'];
                    const batchNo = response.message.batch_id;
                    const itemCode = response.message.item_code[0]['parent'];
                    const expiryDate = response.message.formatted_date;
                    const conversionRate = response.message.conversion_factor[0]['conversion_factor'];

                    frappe.db.get_value('Item', itemCode, 'item_name', function (r) {
                        const itemName = r.item_name;

                        // Always add a new row for each scan
                        let newRow = frm.add_child('items', {
                            item_code: itemCode,
                            item_name: itemName,
                            qty: qty,
                            uom: uom,
                            conversion_factor: conversionRate,
                            batch_no: batchNo,
                            custom_expiry_date: expiryDate,
                            barcode: barcode,
                            received_stock_qty: qty * conversionRate,
                            stock_qty: qty * conversionRate
                        });

                        // Set warehouse from PO if available, else use default warehouse
                        if (frm.doc.custom_purchase_order_name) {
                            frappe.db.get_doc('Purchase Order', frm.doc.custom_purchase_order_name).then(po => {
                                if (po && po.items) {
                                    let po_item = po.items.find(i => i.item_code === itemCode);
                                    if (po_item && po_item.warehouse) {
                                        frappe.model.set_value(newRow.doctype, newRow.name, 'warehouse', po_item.warehouse);
                                    }
                                }
                            });
                        } else if (frm.doc.set_warehouse) {
                            frappe.model.set_value(newRow.doctype, newRow.name, 'warehouse', frm.doc.set_warehouse);
                        }

                        // Refresh the field first
                        frm.refresh_field('items');

                        // Trigger item code change to fetch price list rate
                        frm.script_manager.trigger('item_code', newRow.doctype, newRow.name);

                        // Alternative method to fetch price list rate if above doesn't work
                        setTimeout(() => {
                            frappe.model.set_value(newRow.doctype, newRow.name, 'item_code', itemCode);
                            frm.refresh_field('items');

                            // Calculate totals
                            frm.trigger('calculate_taxes_and_totals');

                            // Update total quantities
                            let total_qty = 0;
                            frm.doc.items.forEach(function (item) {
                                total_qty += flt(item.qty);
                            });
                            frm.set_value('total_qty', total_qty);

                        }, 100);

                        // Clear the barcode field
                        frm.set_value('scan_barcode', '');

                        frappe.show_alert({
                            message: __(`Added ${qty} ${uom} of ${itemName}`),
                            indicator: 'green'
                        });
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
    },

    refresh: function (frm) {
        if (frm.doc.__is_refreshing) return;
        frm.doc.__is_refreshing = true;

        frm.doc.item_map = {};

        setTimeout(() => {
            if (frm.doc.items && frm.doc.items.length > 0 && frm.doc.items[0].barcode) {
                frm.doc.items.forEach(row => {
                    if (row.barcode) {
                        frm.doc.item_map[row.barcode] = {
                            uom: row.uom,
                            itemCode: row.item_code,
                            batchNo: row.batch_no
                        };
                    }
                });
            }
            frm.doc.__is_refreshing = false;
        }, 200);

        if (frm.doc.docstatus === 1) {
            frm.set_read_only();
        }
    },

    onload: function (frm) {
        if (frm.doc.custom_purchase_invoice_name) {
            frappe.db.get_doc('Purchase Invoice', frm.doc.custom_purchase_invoice_name).then(pinv => {
                if (pinv && pinv.custom_is_landed_cost) {
                    frm.set_value('custom_shipment_order_name', pinv.custom_shipment_name_ref || '');
                }
            });
        }
    },
});

// frappe.ui.form.on('Purchase Receipt Item', {
//     // received_stock_qty: function (frm, cdt, cdn) {
//     //     update_total_qty(frm);
//     //     update_base_amount(frm, cdt, cdn); // Add this line
//     // },

//     // items_add: function (frm, cdt, cdn) {
//     //     setTimeout(function () {
//     //         update_purchase_order_and_purchase_invoice_fields(frm);
//     //     }, 500);
//     // },

//     // items_remove: function (frm) {
//     //     update_total_qty(frm);
//     // },

//     // stock_qty: function (frm, cdt, cdn) {
//     //     update_base_amount(frm, cdt, cdn);
//     // },

//     // qty: function (frm, cdt, cdn) {
//     //     let row = locals[cdt][cdn];
//     //     // Always update stock_qty after qty change
//     //     frappe.model.set_value(cdt, cdn, 'stock_qty', (row.qty || 0) * (row.conversion_factor || 1));
//     //     update_base_amount(frm, cdt, cdn); // This will calculate base_amount
//     //     update_total_qty(frm);

//     // },

//     // base_rate: function (frm, cdt, cdn) {
//     //     update_base_amount(frm, cdt, cdn); // Add this line
//     // },

//     // uom: function (frm, cdt, cdn) {
//     //     let row = locals[cdt][cdn];
//     //     // Update received_stock_qty based on UOM
//     //     if (row.uom === 'Unit') {
//     //         frappe.model.set_value(cdt, cdn, 'received_stock_qty', row.qty * (row.conversion_factor || 1));
//     //     }
//     //     update_base_amount(frm, cdt, cdn); // Add this line
//     // },

//     // conversion_factor: function (frm, cdt, cdn) {
//     //     let row = locals[cdt][cdn];
//     //     // Always update stock_qty after conversion factor change
//     //     frappe.model.set_value(cdt, cdn, 'stock_qty', (row.qty || 0) * (row.conversion_factor || 1));
//     //     if (row.uom === 'Unit') {
//     //         frappe.model.set_value(cdt, cdn, 'received_stock_qty', row.qty * (row.conversion_factor || 1));
//     //     }
//     //     update_base_amount(frm, cdt, cdn); // Add this line
//     // },
// });

// FIXED update_base_amount function - Always use qty * base_rate
// function update_base_amount(frm, cdt, cdn) {
//     var row = locals[cdt][cdn];
//     // Always use qty * base_rate regardless of UOM
//     frappe.model.set_value(cdt, cdn, 'base_amount', (row.base_rate || 0) * (row.qty || 0));
//     console.log("Update base amount - UOM:", row.uom, "Qty:", row.qty, "Base Rate:", row.base_rate, "Base Amount:", (row.base_rate || 0) * (row.qty || 0));

//     // Update total amount after changing base_amount
//     update_total_amount(frm);
// }

// function update_total_qty(frm) {
//     let total = 0;

//     (frm.doc.items || []).forEach(item => {
//         total += flt(item.received_stock_qty);
//     });

//     frm.set_value("total_qty", total);
//     frm.refresh_field("total_qty");
// }

// function update_total_amount(frm) {
//     if (frm.doc.custom_purchase_invoice_name) return; // Invoice present, totals come from invoice
//     if (frm.doc.docstatus === 1) return;
//     let total = 0;
//     (frm.doc.items || []).forEach(item => {
//         total += flt(item.base_amount);
//     });
//     frm.set_value("base_total", total);
//     frm.refresh_field("base_total");
// }

// function update_purchase_order_and_purchase_invoice_fields(frm) {
//     if (frm.doc.custom_purchase_order_name || frm.doc.custom_purchase_invoice_name) {
//         frm.doc.items.forEach(item => {
//             if (frm.doc.custom_purchase_order_name) {
//                 frappe.model.set_value(item.doctype, item.name, 'purchase_order', frm.doc.custom_purchase_order_name);
//             }
//             if (frm.doc.custom_purchase_invoice_name) {
//                 frappe.model.set_value(item.doctype, item.name, 'purchase_invoice', frm.doc.custom_purchase_invoice_name);
//             }
//         });
//     }
// }