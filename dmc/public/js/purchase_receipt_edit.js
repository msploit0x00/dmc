
frappe.ui.form.on('Purchase Receipt', {
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

                        // Check if item with same item_code and batch already exists
                        let existingRow = null;
                        if (frm.doc.items && frm.doc.items.length > 0) {
                            // Debug: Log what we're looking for
                            console.log('Looking for:', { itemCode, batchNo, uom });
                            console.log('Existing items:', frm.doc.items.map(i => ({
                                item_code: i.item_code,
                                batch_no: i.batch_no,
                                uom: i.uom
                            })));

                            existingRow = frm.doc.items.find(item =>
                                String(item.item_code).trim() === String(itemCode).trim() &&
                                String(item.batch_no).trim() === String(batchNo).trim() &&
                                String(item.uom).trim() === String(uom).trim()
                            );

                            console.log('Found existing row:', existingRow ? 'YES' : 'NO');
                        }

                        if (existingRow) {
                            // Update existing row quantity
                            let newQty = flt(existingRow.qty) + qty;
                            frappe.model.set_value(existingRow.doctype, existingRow.name, 'qty', newQty);
                            frappe.model.set_value(existingRow.doctype, existingRow.name, 'received_stock_qty', newQty * conversionRate);
                            frappe.model.set_value(existingRow.doctype, existingRow.name, 'stock_qty', newQty * conversionRate);

                            frm.refresh_field('items');
                            frm.trigger('calculate_taxes_and_totals');

                            // Update total quantities
                            let total_qty = 0;
                            frm.doc.items.forEach(function (item) {
                                total_qty += flt(item.qty);
                            });
                            frm.set_value('total_qty', total_qty);

                            frappe.show_alert({
                                message: __(`Updated to ${newQty} ${uom} of ${itemName}`),
                                indicator: 'blue'
                            });
                        } else {
                            // Add new row if not exists
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

                            frappe.show_alert({
                                message: __(`Added ${qty} ${uom} of ${itemName}`),
                                indicator: 'green'
                            });
                        }

                        // Clear the barcode field
                        frm.set_value('scan_barcode', '');
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

