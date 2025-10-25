// ========================================
// MAIN PURCHASE RECEIPT SCRIPT - WITH CASE-INSENSITIVE BATCH VALIDATION
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
                                item.batch_no.trim().toUpperCase() === batchNo.trim().toUpperCase() &&
                                item.item_code === itemCode
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

                            // Use the correct batch number from PI (preserves case)
                            const correctBatchNo = matchedPIItem.batch_no;

                            process_scanned_item(frm, {
                                barcode,
                                batchNo: correctBatchNo,  // Use correct batch from system
                                itemCode,
                                uom,
                                conversionRate,
                                expiryDate
                            });
                        }
                    });
                } else {
                    const matchedPIItem = frm._pi_items.find(item =>
                        item.batch_no.trim().toUpperCase() === batchNo.trim().toUpperCase() &&
                        item.item_code === itemCode
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

                    // Use the correct batch number from PI (preserves case)
                    const correctBatchNo = matchedPIItem.batch_no;

                    process_scanned_item(frm, {
                        barcode,
                        batchNo: correctBatchNo,  // Use correct batch from system
                        itemCode,
                        uom,
                        conversionRate,
                        expiryDate
                    });
                }
            }
        });
    },
    set_warehouse: function (frm) {
        if (!frm.doc.custom_scanned_items || frm.doc.custom_scanned_items.length === 0) {
            return;
        }

        const newWarehouse = frm.doc.set_warehouse;

        // Update warehouse for all scanned items
        frm.doc.custom_scanned_items.forEach(scannedItem => {
            if (newWarehouse) {
                scannedItem.warehouse = newWarehouse;
            } else {
                // If set_warehouse is cleared, fetch item's default warehouse
                frappe.call({
                    method: 'frappe.client.get',
                    args: {
                        doctype: 'Item',
                        name: scannedItem.item_code
                    },
                    async: false,
                    callback: function (response) {
                        if (response.message && response.message.item_defaults) {
                            const itemDefault = response.message.item_defaults.find(d => d.company === frm.doc.company);
                            if (itemDefault && itemDefault.default_warehouse) {
                                scannedItem.warehouse = itemDefault.default_warehouse;
                            } else {
                                scannedItem.warehouse = '';
                            }
                        }
                    }
                });
            }
        });

        frm.refresh_field('custom_scanned_items');

        // Also update the main items table
        aggregate_scanned_to_items(frm);
        frm.refresh_field('items');
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

    // First, get the correct batch number from system (case-insensitive search)
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Batch',
            filters: {
                'name': ['like', batchNo]
            },
            fields: ['name', 'item']
        },
        callback: function (batchResponse) {
            let correctBatchNo = batchNo;

            // Find exact match (case-insensitive)
            if (batchResponse.message && batchResponse.message.length > 0) {
                const matchedBatch = batchResponse.message.find(b =>
                    b.name.toUpperCase() === batchNo.toUpperCase() &&
                    b.item === itemCode
                );

                if (matchedBatch) {
                    correctBatchNo = matchedBatch.name; // Use the correct case from system
                }
            }

            // Now get the full Item document to access defaults
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Item',
                    name: itemCode
                },
                callback: function (response) {
                    if (!response.message) {
                        frappe.msgprint(__("Could not fetch Item details."));
                        frm.set_value('scan_barcode', '');
                        return;
                    }

                    const item = response.message;
                    const itemName = item.item_name;

                    // Find default warehouse for the current company
                    let defaultWarehouse = '';
                    if (item.item_defaults && item.item_defaults.length > 0) {
                        const itemDefault = item.item_defaults.find(d => d.company === frm.doc.company);
                        if (itemDefault && itemDefault.default_warehouse) {
                            defaultWarehouse = itemDefault.default_warehouse;
                        }
                    }

                    // Determine which warehouse to use (for receiving)
                    const warehouseToUse = frm.doc.set_warehouse || defaultWarehouse || '';

                    // Determine which accepted warehouse to use
                    const acceptedWarehouseToUse = frm.doc.custom_set_accepted_warehouse || defaultWarehouse || '';

                    let existingScannedRow = null;
                    if (frm.doc.custom_scanned_items && frm.doc.custom_scanned_items.length > 0) {
                        existingScannedRow = frm.doc.custom_scanned_items.find(item =>
                            String(item.item_code).trim() === String(itemCode).trim() &&
                            String(item.batch_no).trim().toUpperCase() === String(batchNo).trim().toUpperCase() &&
                            String(item.uom).trim() === String(uom).trim()
                        );
                    }

                    if (existingScannedRow) {
                        let newReceivedQty = flt(existingScannedRow.received_qty) + 1;
                        let newReceivedStockQty = newReceivedQty * conversionRate;

                        existingScannedRow.received_qty = newReceivedQty;
                        existingScannedRow.received_stock_qty = newReceivedStockQty;
                        existingScannedRow.stock_qty = newReceivedStockQty;

                        // Update batch_no to match system (fix case)
                        existingScannedRow.batch_no = batchNo;

                        // Update warehouse if it's different
                        if (warehouseToUse) {
                            existingScannedRow.warehouse = warehouseToUse;
                        }

                        // Update accepted warehouse if it's different
                        if (acceptedWarehouseToUse) {
                            existingScannedRow.accepted_warehouse = acceptedWarehouseToUse;
                        }
                    } else {
                        frm.add_child('custom_scanned_items', {
                            item_code: itemCode,
                            item_name: itemName,
                            batch_no: batchNo,  // This now has the correct case from PI
                            uom: uom,
                            conversion_factor: conversionRate,
                            received_qty: 1,
                            received_stock_qty: 1 * conversionRate,
                            stock_qty: 1 * conversionRate,
                            barcode: barcode,
                            warehouse: warehouseToUse,
                            accepted_warehouse: acceptedWarehouseToUse
                        });
                    }

                    frm.set_value('scan_barcode', '');

                    debounced_aggregate_and_refresh(frm);
                }
            });
        }
    })

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
            const key = `${scannedItem.item_code}_${scannedItem.batch_no.toUpperCase()}`;

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
            const key = `${item.item_code}_${item.batch_no.toUpperCase()}`;

            if (aggregateMap[key]) {
                const aggregatedReceivedQty = aggregateMap[key].total_received_stock_qty;

                item.received_stock_qty = aggregatedReceivedQty;

                if (item.conversion_factor && item.conversion_factor > 0) {
                    item.received_qty = aggregatedReceivedQty / item.conversion_factor;
                }

                // Update warehouse and accepted_warehouse from scanned items
                const scannedItem = frm.doc.custom_scanned_items.find(si =>
                    si.item_code === item.item_code &&
                    si.batch_no.toUpperCase() === item.batch_no.toUpperCase()
                );
                if (scannedItem) {
                    if (scannedItem.warehouse) {
                        item.warehouse = scannedItem.warehouse;
                    }
                    if (scannedItem.accepted_warehouse) {
                        item.accepted_warehouse = scannedItem.accepted_warehouse;
                    }
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
                            piItemMap[itemCode].batches.push(batchNo.toUpperCase());
                            piBatchMap[batchNo.toUpperCase()] = itemCode;
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

                        if (batchNo && !piBatchMap[batchNo.toUpperCase()]) {
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
                    item => item.batch_no.toUpperCase() === row.batch_no.toUpperCase() &&
                        item.item_code === row.item_code
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
    })
}