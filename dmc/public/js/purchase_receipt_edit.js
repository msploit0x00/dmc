// ========================================
// PURCHASE RECEIPT SCRIPT - SIMPLIFIED (NO PRICE TRANSFER)
// ========================================

let aggregateTimeout = null;
let refreshTimeout = null;

frappe.ui.form.on('Purchase Receipt', {
    scan_barcode: function (frm) {
        if (!frm.doc.scan_barcode) return;

        const barcode = frm.doc.scan_barcode;

        // ✅ CRITICAL: Prevent Frappe from auto-adding to main items table
        frm._scanning = true;

        // Clear the barcode field immediately to prevent default behavior
        setTimeout(() => {
            frm.set_value('scan_barcode', '');
        }, 50);

        frappe.call({
            method: 'dmc.barcode_details.get_barcode_details',
            args: { barcode },
            callback: function (response) {
                // ✅ VALIDATION 1: Check if barcode is valid
                if (!response.message) {
                    frappe.msgprint({
                        title: __('Invalid Barcode'),
                        message: __(`❌ <b>Barcode not found!</b><br><br>
                                    Barcode: <b>${barcode}</b><br><br>
                                    Please scan a valid barcode.`),
                        indicator: 'red'
                    });
                    return;
                }

                // ✅ VALIDATION 2: Check if all required data exists
                if (!response.message.barcode_uom || !response.message.barcode_uom[0] ||
                    !response.message.item_code || !response.message.item_code[0] ||
                    !response.message.conversion_factor || !response.message.conversion_factor[0]) {
                    frappe.msgprint({
                        title: __('Incomplete Barcode Data'),
                        message: __(`❌ <b>Barcode data is incomplete!</b><br><br>
                                    Barcode: <b>${barcode}</b><br><br>
                                    Missing required information. Please check the barcode setup.`),
                        indicator: 'red'
                    });
                    return;
                }

                const uom = response.message.barcode_uom[0]['uom'];
                const batchNo = response.message.batch_id;
                const itemCode = response.message.item_code[0]['parent'];
                const expiryDate = response.message.formatted_date;
                const conversionRate = response.message.conversion_factor[0]['conversion_factor'];

                // ✅ VALIDATION 3: Check if UOM exists
                if (!uom || uom.trim() === '') {
                    frappe.msgprint({
                        title: __('Missing UOM'),
                        message: __(`❌ <b>UOM is missing!</b><br><br>
                                    Item: <b>${itemCode}</b><br>
                                    Barcode: <b>${barcode}</b><br><br>
                                    Please add a UOM to this barcode.`),
                        indicator: 'red'
                    });
                    return;
                }

                // ✅ VALIDATION 4: Check if conversion factor exists
                if (!conversionRate || conversionRate <= 0) {
                    frappe.msgprint({
                        title: __('Missing Conversion Factor'),
                        message: __(`⚠️ <b>Cannot scan this barcode!</b><br><br>
                                    Item: <b>${itemCode}</b><br>
                                    UOM: <b>${uom}</b><br><br>
                                    ❌ This UOM does not have a conversion factor defined.<br><br>
                                    📋 Please go to the Item master and add the conversion factor for this UOM before scanning.`),
                        indicator: 'red',
                        primary_action: {
                            label: __('Open Item'),
                            action: function () {
                                frappe.set_route('Form', 'Item', itemCode);
                            }
                        }
                    });
                    return;
                }

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
                                // Barcode already cleared above
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
                                // Barcode already cleared above
                                return;
                            }

                            const correctBatchNo = matchedPIItem.batch_no;

                            process_scanned_item(frm, {
                                barcode,
                                batchNo: correctBatchNo,
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
                        // Barcode already cleared above
                        return;
                    }

                    const correctBatchNo = matchedPIItem.batch_no;

                    process_scanned_item(frm, {
                        barcode,
                        batchNo: correctBatchNo,
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

        frm.doc.custom_scanned_items.forEach(scannedItem => {
            if (newWarehouse) {
                scannedItem.warehouse = newWarehouse;
            } else {
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
        sync_scanned_to_main_items(frm);
        frm.refresh_field('items');
    },

    items_add: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Mark this row as manually added (not from scan)
        row._manually_added = true;

        // Set purchase order if available
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

        frm._pi_items = null;
        frm._pi_name = null;

        // ✅ Prevent Frappe default barcode behavior
        frm._scanning = false;

        // Override the scan_barcode field to prevent default item addition
        if (frm.fields_dict.scan_barcode) {
            frm.fields_dict.scan_barcode.df.onchange = null;
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
        // Sync scanned items to main table before saving
        sync_scanned_to_main_items(frm);
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

    // ✅ VALIDATION: Double-check all required fields before processing
    if (!itemCode || !batchNo || !uom || !conversionRate || conversionRate <= 0) {
        frappe.msgprint({
            title: __('Invalid Data'),
            message: __(`❌ <b>Cannot process scanned item!</b><br><br>
                        Missing or invalid data. Please check the barcode setup.`),
            indicator: 'red'
        });
        return;
    }

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

            if (batchResponse.message && batchResponse.message.length > 0) {
                const matchedBatch = batchResponse.message.find(b =>
                    b.name.toUpperCase() === batchNo.toUpperCase() &&
                    b.item === itemCode
                );

                if (matchedBatch) {
                    correctBatchNo = matchedBatch.name;
                }
            }

            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Item',
                    name: itemCode
                },
                callback: function (response) {
                    if (!response.message) {
                        frappe.msgprint({
                            title: __('Item Not Found'),
                            message: __(`❌ <b>Item does not exist!</b><br><br>
                                        Item Code: <b>${itemCode}</b><br><br>
                                        Please check if the item exists in the system.`),
                            indicator: 'red'
                        });
                        return;
                    }

                    const item = response.message;
                    const itemName = item.item_name;

                    let defaultWarehouse = '';
                    if (item.item_defaults && item.item_defaults.length > 0) {
                        const itemDefault = item.item_defaults.find(d => d.company === frm.doc.company);
                        if (itemDefault && itemDefault.default_warehouse) {
                            defaultWarehouse = itemDefault.default_warehouse;
                        }
                    }

                    const warehouseToUse = frm.doc.set_warehouse || defaultWarehouse || '';
                    const acceptedWarehouseToUse = frm.doc.custom_set_accepted_warehouse || defaultWarehouse || '';

                    let existingScannedRow = null;
                    if (frm.doc.custom_scanned_items && frm.doc.custom_scanned_items.length > 0) {
                        existingScannedRow = frm.doc.custom_scanned_items.find(item =>
                            String(item.item_code).trim() === String(itemCode).trim() &&
                            String(item.batch_no).trim().toUpperCase() === String(correctBatchNo).trim().toUpperCase() &&
                            String(item.uom).trim() === String(uom).trim()
                        );
                    }

                    if (existingScannedRow) {
                        let newReceivedQty = flt(existingScannedRow.received_qty) + 1;
                        let newReceivedStockQty = newReceivedQty * conversionRate;

                        // ✅ Update existing row
                        existingScannedRow.received_qty = newReceivedQty;
                        existingScannedRow.received_stock_qty = newReceivedStockQty;
                        existingScannedRow.stock_qty = newReceivedStockQty;
                        existingScannedRow.batch_no = correctBatchNo;

                        if (warehouseToUse) {
                            existingScannedRow.warehouse = warehouseToUse;
                        }
                        if (acceptedWarehouseToUse) {
                            existingScannedRow.accepted_warehouse = acceptedWarehouseToUse;
                        }

                        frappe.show_alert({
                            message: __(`✅ Updated: ${itemName} - Qty: ${newReceivedQty}`),
                            indicator: 'green'
                        }, 3);
                    } else {
                        // ✅ Add new row
                        frm.add_child('custom_scanned_items', {
                            item_code: itemCode,
                            item_name: itemName,
                            batch_no: correctBatchNo,
                            uom: uom,
                            conversion_factor: conversionRate,
                            received_qty: 1,
                            received_stock_qty: 1 * conversionRate,
                            stock_qty: 1 * conversionRate,
                            barcode: barcode,
                            warehouse: warehouseToUse,
                            accepted_warehouse: acceptedWarehouseToUse
                        });

                        frappe.show_alert({
                            message: __(`✅ Added: ${itemName} - Qty: 1`),
                            indicator: 'green'
                        }, 3);
                    }

                    frm.set_value('scan_barcode', '');
                    debounced_sync_and_refresh(frm);
                }
            });
        }
    });
}

function debounced_sync_and_refresh(frm) {
    if (aggregateTimeout) clearTimeout(aggregateTimeout);

    aggregateTimeout = setTimeout(() => {
        sync_scanned_to_main_items(frm);

        if (refreshTimeout) clearTimeout(refreshTimeout);
        refreshTimeout = setTimeout(() => {
            frm.refresh_field('custom_scanned_items');
            frm.refresh_field('items');
        }, 100);
    }, 400);
}

function sync_scanned_to_main_items(frm) {
    if (!frm.doc.custom_scanned_items || frm.doc.custom_scanned_items.length === 0) {
        return;
    }

    // Create a map of scanned items grouped by item_code + batch_no
    const scannedMap = {};

    frm.doc.custom_scanned_items.forEach(scannedItem => {
        const key = `${scannedItem.item_code}_${scannedItem.batch_no.toUpperCase()}`;

        if (!scannedMap[key]) {
            scannedMap[key] = {
                item_code: scannedItem.item_code,
                item_name: scannedItem.item_name,
                batch_no: scannedItem.batch_no,
                uom: scannedItem.uom,
                conversion_factor: scannedItem.conversion_factor,
                warehouse: scannedItem.warehouse,
                accepted_warehouse: scannedItem.accepted_warehouse,
                total_received_qty: 0,
                total_received_stock_qty: 0
            };
        }

        scannedMap[key].total_received_qty += flt(scannedItem.received_qty);
        scannedMap[key].total_received_stock_qty += flt(scannedItem.received_stock_qty);
    });

    // Initialize items array if empty
    if (!frm.doc.items) {
        frm.doc.items = [];
    }

    // Track which scanned items were found in main table
    const processedKeys = new Set();

    // Update existing items in main table with scanned quantities
    frm.doc.items.forEach(item => {
        const key = `${item.item_code}_${(item.batch_no || '').toUpperCase()}`;

        if (scannedMap[key]) {
            const scannedData = scannedMap[key];

            // Update quantities only
            item.received_qty = scannedData.total_received_qty;
            item.received_stock_qty = scannedData.total_received_stock_qty;
            item.stock_qty = scannedData.total_received_stock_qty;

            // Update warehouses
            if (scannedData.warehouse) {
                item.warehouse = scannedData.warehouse;
            }
            if (scannedData.accepted_warehouse) {
                item.accepted_warehouse = scannedData.accepted_warehouse;
            }

            // Mark this scanned item as processed
            processedKeys.add(key);
        }
    });

    // Add new items that don't exist in main table yet
    Object.keys(scannedMap).forEach(key => {
        if (!processedKeys.has(key)) {
            const scannedData = scannedMap[key];

            const newItem = {
                item_code: scannedData.item_code,
                item_name: scannedData.item_name,
                batch_no: scannedData.batch_no,
                uom: scannedData.uom,
                conversion_factor: scannedData.conversion_factor,
                qty: scannedData.total_received_qty,
                received_qty: scannedData.total_received_qty,
                stock_qty: scannedData.total_received_stock_qty,
                received_stock_qty: scannedData.total_received_stock_qty,
                warehouse: scannedData.warehouse,
                accepted_warehouse: scannedData.accepted_warehouse
            };

            // Set purchase order if available
            if (frm.doc.custom_purchase_order_name) {
                newItem.purchase_order = frm.doc.custom_purchase_order_name;
            }

            frm.doc.items.push(newItem);
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

                    // Skip validation for manually added items
                    if (item._manually_added) {
                        continue;
                    }

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

        debounced_sync_and_refresh(frm);
    },

    received_stock_qty: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        if (row.conversion_factor && row.conversion_factor > 0) {
            const newReceivedQty = flt(row.received_stock_qty) / flt(row.conversion_factor);

            row.received_qty = newReceivedQty;
            row.stock_qty = flt(row.received_stock_qty);
        }

        debounced_sync_and_refresh(frm);
    }
});