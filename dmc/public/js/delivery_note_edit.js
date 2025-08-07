// // ============================

frappe.ui.form.on('Delivery Note', {
    onload: function (frm) {
        if (frm.is_new() && frm.doc.items && frm.doc.items.length == 1) {
            if (!frm.doc.items[0].barcode && !frm.doc.items[0].item_code) {
                frm.clear_table("items");
            }
        }
        frm._updating_from_scan = false;

        // ✅ INTERCEPT ERPNext's calculate_taxes_and_totals to protect our amounts
        // setup_calculate_interceptor(frm);

        // ✅ DELAYED check for free items (wait for all data to load)
        setTimeout(() => {
            check_and_toggle_free_scanner(frm);
            // ✅ FORCE total quantity calculation on load
            update_total_qty(frm);
        }, 2000);
    },

    refresh: function (frm) {
        // ✅ ENSURE interceptor is always active
        // setup_calculate_interceptor(frm);

        setTimeout(() => {
            check_and_toggle_free_scanner(frm);
            update_total_qty(frm);
        }, 500);
    },

    // 🔥 BEFORE SAVE - Store our custom calculations
    before_save: function (frm) {
        console.log('📝 Before save - storing custom amounts...');

        // Store custom amounts for each item
        frm._stored_custom_amounts = {};
        frm._stored_totals = {
            total_qty: frm.doc.total_qty,
            net_total: frm.doc.net_total,
            total: frm.doc.total,
            grand_total: frm.doc.grand_total
        };

        if (frm.doc.items) {
            frm.doc.items.forEach((row) => {
                if (row.name) {
                    frm._stored_custom_amounts[row.name] = {
                        amount: row.amount,
                        rate: row.rate,
                        qty: row.qty,
                        stock_qty: row.stock_qty,
                        uom: row.uom
                    };
                }
            });
        }

        console.log('📝 Stored custom amounts:', frm._stored_custom_amounts);
        console.log('📝 Stored totals:', frm._stored_totals);
    },

    // 🔥 AFTER SAVE - Restore our custom calculations
    // after_save: function (frm) {
    //     console.log('💾 After save - restoring custom amounts...');

    //     if (frm._stored_custom_amounts && frm._stored_totals) {
    //         // Flag to prevent loops
    //         frm._restoring_after_save = true;

    //         // Restore item amounts
    //         setTimeout(() => {
    //             let amounts_changed = false;

    //             if (frm.doc.items) {
    //                 frm.doc.items.forEach((row) => {
    //                     if (row.name && frm._stored_custom_amounts[row.name]) {
    //                         const stored = frm._stored_custom_amounts[row.name];

    //                         // Check if UOM logic should apply
    //                         const uomLower = (row.uom || '').toLowerCase().trim();
    //                         const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uomLower);

    //                         let expectedAmount;
    //                         if (row.is_free_item) {
    //                             expectedAmount = 0;
    //                         } else if (isUnitUOM) {
    //                             expectedAmount = flt(row.rate) * flt(row.qty);
    //                         } else {
    //                             expectedAmount = flt(row.rate) * flt(row.stock_qty);
    //                         }

    //                         // If amount changed, restore it
    //                         if (Math.abs(row.amount - expectedAmount) > 0.01) {
    //                             console.log(`💾 Restoring amount for ${row.item_code}: ${row.amount} → ${expectedAmount}`);
    //                             frappe.model.set_value(row.doctype, row.name, 'amount', expectedAmount);
    //                             amounts_changed = true;
    //                         }
    //                     }
    //                 });
    //             }

    //             if (amounts_changed) {
    //                 // Recalculate totals
    //                 setTimeout(() => {
    //                     update_total_qty(frm);
    //                     frm.script_manager.trigger("calculate_taxes_and_totals");

    //                     // Show message
    //                     frappe.show_alert({
    //                         message: __('Custom calculations restored after save'),
    //                         indicator: 'blue'
    //                     });

    //                     frm._restoring_after_save = false;
    //                 }, 500);
    //             } else {
    //                 frm._restoring_after_save = false;
    //             }
    //         }, 1000);
    //     }
    // },

    after_submit: function (frm) {
        console.log('📤 After submit - fixing taxes and calculations...');

        // Flag to prevent loops during restoration
        frm._restoring_after_submit = true;

        setTimeout(() => {
            console.log('🔄 Recalculating everything after submit...');

            // STEP 1: Fix all item amounts based on UOM logic
            let correct_net_total = 0;
            let amounts_fixed = false;

            if (frm.doc.items) {
                frm.doc.items.forEach((item, index) => {
                    if (!item || item.__deleted) return;

                    const uomLower = (item.uom || '').toLowerCase().trim();
                    const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uomLower);

                    let correctAmount;
                    if (item.is_free_item) {
                        correctAmount = 0;
                    } else if (isUnitUOM) {
                        correctAmount = flt(item.rate) * flt(item.qty);
                    } else {
                        correctAmount = flt(item.rate) * flt(item.stock_qty);
                    }

                    // Check if amount needs fixing
                    if (Math.abs(flt(item.amount) - correctAmount) > 0.01) {
                        console.log(`🔧 After submit - fixing amount for ${item.item_code}: ${item.amount} → ${correctAmount}`);
                        item.amount = correctAmount;
                        amounts_fixed = true;
                    }

                    correct_net_total += correctAmount;
                });
            }

            // STEP 2: Update document totals
            if (amounts_fixed || Math.abs(flt(frm.doc.net_total) - correct_net_total) > 0.01) {
                console.log(`🔧 After submit - fixing net_total: ${frm.doc.net_total} → ${correct_net_total}`);
                frm.doc.net_total = correct_net_total;
                frm.doc.total = correct_net_total;
                frm.doc.base_net_total = correct_net_total * (frm.doc.conversion_rate || 1);
                frm.doc.base_total = correct_net_total * (frm.doc.conversion_rate || 1);
            }

            // STEP 3: Recalculate taxes with proper UOM logic
            if (frm.doc.taxes && frm.doc.taxes.length > 0) {
                let cumulative_total = correct_net_total;
                let taxes_fixed = false;

                frm.doc.taxes.forEach((tax, tax_index) => {
                    if (tax.charge_type === "On Net Total") {
                        const correct_tax_amount = flt(correct_net_total * flt(tax.rate) / 100);
                        cumulative_total += correct_tax_amount;

                        if (Math.abs(flt(tax.tax_amount) - correct_tax_amount) > 0.01) {
                            console.log(`🔧 After submit - fixing tax ${tax_index + 1}: ${tax.tax_amount} → ${correct_tax_amount}`);
                            tax.tax_amount = correct_tax_amount;
                            tax.base_tax_amount = correct_tax_amount * (frm.doc.conversion_rate || 1);
                            tax.total = cumulative_total;
                            tax.base_total = cumulative_total * (frm.doc.conversion_rate || 1);
                            taxes_fixed = true;
                        }
                    }
                });

                // Update grand total
                if (Math.abs(flt(frm.doc.grand_total) - cumulative_total) > 0.01) {
                    console.log(`🔧 After submit - fixing grand_total: ${frm.doc.grand_total} → ${cumulative_total}`);
                    frm.doc.grand_total = cumulative_total;
                    frm.doc.base_grand_total = cumulative_total * (frm.doc.conversion_rate || 1);
                }

                if (taxes_fixed) {
                    console.log('✅ Taxes recalculated after submit');
                }
            }

            // STEP 4: Update total_qty
            update_total_qty(frm);

            // STEP 5: Refresh all fields to show corrected values
            setTimeout(() => {
                frm.refresh_field('items');
                frm.refresh_field('total_qty');
                frm.refresh_field('net_total');
                frm.refresh_field('total');
                frm.refresh_field('taxes');
                frm.refresh_field('grand_total');

                // Show completion message
                frappe.show_alert({
                    message: __('Calculations corrected after submission'),
                    indicator: 'green'
                });

                frm._restoring_after_submit = false;
                console.log('✅ After submit calculations completed');
            }, 500);

        }, 1000); // Wait 1 second after submit to ensure all processes are complete
    },

    refresh: function (frm) {
        if (frm.doc.__is_refreshing) return;
        frm.doc.__is_refreshing = true;
        update_total_qty(frm);

        // ✅ ONLY check free scanner once per refresh and with delay
        if (!frm._free_scanner_checked && !frm._checking_free_scanner) {
            setTimeout(() => {
                check_and_toggle_free_scanner(frm);
                frm._free_scanner_checked = true;
            }, 1500);
        }

        // ✅ Reset refresh flag after short delay
        setTimeout(() => {
            frm.doc.__is_refreshing = false;
        }, 100);

        // 🔥 AUTOMATIC CALCULATION - No manual buttons needed
        // ✅ FORCE total calculation on refresh (for existing data)
        setTimeout(() => {
            update_total_qty(frm);
            calculate_document_totals(frm);
            console.log('🔄 Auto-calculations completed on refresh');

            // 🔥 ENABLE AUTOMATIC PROTECTION - Keeps values correct continuously
            if (!frm._auto_protect_enabled) {
                frm._auto_protect_enabled = true;
                frm._auto_protect_interval = setInterval(() => {
                    if (frm.doc && frm.doc.items && frm.doc.items.length > 0 && !frm._updating_from_scan) {
                        console.log('🛡️ Auto-protecting values...');

                        // Ensure amounts are correct
                        let should_update = false;
                        frm.doc.items.forEach((item, index) => {
                            if (!item || item.__deleted) return;

                            const uomLower = (item.uom || '').toLowerCase().trim();
                            const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uomLower);

                            let correct_amount;
                            if (item.is_free_item) {
                                correct_amount = 0;
                            } else {
                                if (isUnitUOM) {
                                    correct_amount = flt((item.rate || 0) * (item.qty || 0), 2);
                                } else {
                                    correct_amount = flt((item.rate || 0) * (item.stock_qty || 0), 2);
                                }
                            }

                            if (Math.abs(flt(item.amount) - correct_amount) > 0.01) {
                                console.log(`🔧 Auto-fixing amount for ${item.item_code}: ${item.amount} → ${correct_amount}`);
                                item.amount = correct_amount;
                                frappe.model.set_value(item.doctype, item.name, 'amount', correct_amount);
                                should_update = true;
                            }
                        });

                        if (should_update) {
                            setTimeout(() => {
                                calculate_document_totals(frm);
                                setTimeout(() => {
                                    // refresh_taxes_on_net_total_change(frm, frm.doc.net_total);
                                }, 200);
                            }, 100);
                        }
                    }
                }, 5000); // Check every 5 seconds
                console.log('🛡️ Auto-protection ENABLED - will keep values correct automatically');
            }
        }, 1000);


    },
    // ✅ NORMAL SCANNER
    custom_scan_barcodes: function (frm) {
        if (!frm.doc.custom_scan_barcodes) return;

        const barcode = frm.doc.custom_scan_barcodes;

        // ✅ PREVENT RAPID DOUBLE-SCANNING
        const now = Date.now();
        if (frm._last_scan_time && (now - frm._last_scan_time) < 1000) {
            console.log('🚫 Ignoring rapid double-scan');
            frm.set_value('custom_scan_barcodes', '');
            return;
        }
        frm._last_scan_time = now;

        console.log('📱 SCAN STARTED:', barcode);

        frappe.call({
            method: 'dmc.barcode_details.get_barcode_details',
            args: { barcode: barcode },
            async: false,
            callback: function (response) {
                if (!response.message) return;

                const data = response.message;
                const uom = data.barcode_uom?.[0]?.uom;
                const batchNo = data.batch_id;
                const itemCode = data.item_code?.[0]?.parent;
                const expiryDate = data.formatted_date;
                const conversionRate = data.conversion_factor?.[0]?.conversion_factor || 1;
                const so_detail_id = data.so_detail_id || null;

                console.log("🧾 Sales Order Detail ID:", so_detail_id);

                const findSalesOrderReference = function () {
                    if (frm.doc.sales_order) return frm.doc.sales_order;

                    for (let item of frm.doc.items || []) {
                        if (item.against_sales_order) return item.against_sales_order;
                    }

                    for (let ref of frm.doc.custom_ref || []) {
                        if (ref.custom_against_sales_order) return ref.custom_against_sales_order;
                    }

                    return null;
                };

                const salesOrderRef = findSalesOrderReference();

                frappe.db.get_value('Item', itemCode, 'item_name', function (r) {
                    const itemName = r.item_name;

                    const existingRow = frm.doc.items.find(item =>
                        item.item_code === itemCode &&
                        item.batch_no === batchNo &&
                        !item.is_free_item
                    );

                    const handleRateAndUpdate = (correctRate, isFreeItem = false) => {
                        const finalRate = isFreeItem ? 0 : (correctRate > 0 ? correctRate : 0);

                        if (existingRow) {
                            const newQty = (existingRow.qty || 0) + 1;
                            const uomLower = (existingRow.uom || '').toLowerCase().trim();
                            const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uomLower);
                            const convFactor = existingRow.conversion_factor || conversionRate || 1;
                            const newStockQty = isUnitUOM ? newQty : newQty * convFactor;
                            const newAmount = isFreeItem ? 0 : finalRate * (isUnitUOM ? newQty : newStockQty);

                            existingRow.qty = newQty;
                            existingRow.stock_qty = newStockQty;
                            existingRow.rate = finalRate;
                            existingRow.amount = newAmount;
                            existingRow.custom_out_qty = newQty;
                            existingRow.barcode = barcode;

                            if (!frm._custom_amounts) frm._custom_amounts = {};
                            frm._custom_amounts[existingRow.name] = newAmount;

                            setTimeout(() => {
                                Promise.all([
                                    frappe.model.set_value(existingRow.doctype, existingRow.name, 'qty', newQty),
                                    frappe.model.set_value(existingRow.doctype, existingRow.name, 'stock_qty', newStockQty),
                                    frappe.model.set_value(existingRow.doctype, existingRow.name, 'rate', finalRate),
                                    frappe.model.set_value(existingRow.doctype, existingRow.name, 'amount', newAmount),
                                    frappe.model.set_value(existingRow.doctype, existingRow.name, 'custom_out_qty', newQty),
                                    frappe.model.set_value(existingRow.doctype, existingRow.name, 'barcode', barcode)
                                ]).then(() => {
                                    update_total_qty(frm);
                                    calculate_document_totals(frm);
                                    setTimeout(() => {
                                        frm.refresh_fields(['items', 'total', 'net_total']);
                                        // refresh_taxes_on_net_total_change(frm, frm.doc.net_total);
                                        frm._updating_from_scan = false;
                                        frm._force_no_triggers = false;
                                        frm.set_value('custom_scan_barcodes', '');

                                        frappe.show_alert({
                                            message: __(`Updated quantity to ${newQty} for ${itemName}`),
                                            indicator: 'blue'
                                        });
                                    }, 300);
                                });
                            }, 100);
                            return;
                        }

                        // ✅ New row logic
                        const newRow = frm.add_child('items');
                        const uomLower = (uom || '').toLowerCase().trim();
                        const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uomLower);
                        const stockQty = isUnitUOM ? 1 : (conversionRate || 1);
                        const amount = isFreeItem ? 0 : finalRate * (isUnitUOM ? 1 : stockQty);

                        if (!frm._custom_amounts) frm._custom_amounts = {};
                        frm._custom_amounts[newRow.name] = amount;

                        const baseFields = [
                            ['item_code', itemCode],
                            ['item_name', itemName],
                            ['qty', 1],
                            ['uom', uom],
                            ['conversion_factor', conversionRate],
                            ['stock_qty', stockQty],
                            ['batch_no', batchNo],
                            ['custom_expiry_date', expiryDate],
                            ['barcode', barcode],
                            ['rate', finalRate],
                            ['amount', amount],
                            ['custom_out_qty', 1],
                            ['is_free_item', isFreeItem ? 1 : 0]
                        ];

                        const promises = baseFields.map(([key, val]) =>
                            frappe.model.set_value(newRow.doctype, newRow.name, key, val)
                        );

                        // Add SO references only if valid
                        if (salesOrderRef) {
                            promises.push(frappe.model.set_value(newRow.doctype, newRow.name, 'against_sales_order', salesOrderRef));
                            if (so_detail_id) {
                                promises.push(frappe.model.set_value(newRow.doctype, newRow.name, 'so_detail', so_detail_id));
                            }
                        }

                        Promise.all(promises).then(() => {
                            frm.refresh_field('items');
                            update_total_qty(frm);
                            calculate_document_totals(frm);
                            setTimeout(() => {
                                // refresh_taxes_on_net_total_change(frm, frm.doc.net_total);
                                frm.set_value('custom_scan_barcodes', '');
                                frappe.show_alert({
                                    message: __(`Added 1 ${uom} of ${itemName}`),
                                    indicator: 'green'
                                });
                            }, 200);
                        });
                    };

                    if (salesOrderRef) {
                        frappe.db.get_doc('Sales Order', salesOrderRef).then(soDoc => {
                            let soItem = so_detail_id
                                ? soDoc.items.find(i => i.name === so_detail_id)
                                : soDoc.items.find(i => i.item_code === itemCode);

                            const rateToUse = soItem?.rate || 0;
                            const isFreeItem = soItem?.is_free_item === 1 || soItem?.custom_is_free_item === 1;
                            handleRateAndUpdate(rateToUse, isFreeItem);
                        }).catch(() => {
                            handleRateAndUpdate(0, false);
                        });
                    } else {
                        handleRateAndUpdate(0, false);
                    }
                });
            }
        });
    },

    // ✅ FREE ITEM SCANNER
    custom_scan_barcodes_for_free_items: function (frm) {
        if (!frm.doc.custom_scan_barcodes_for_free_items) return;

        const barcode = frm.doc.custom_scan_barcodes_for_free_items;

        frappe.call({
            method: 'dmc.barcode_details.get_barcode_details',
            args: { barcode: barcode },
            async: false,
            callback: function (response) {
                if (!response.message) {
                    frappe.msgprint(__("Barcode not found"));
                    return;
                }

                const data = response.message;
                const uom = data.barcode_uom?.[0]?.uom;
                const batchNo = data.batch_id;
                const itemCode = data.item_code?.[0]?.parent;
                const expiryDate = data.formatted_date;
                const conversionRate = data.conversion_factor?.[0]?.conversion_factor || 1;

                check_if_item_is_free_in_sales_order(frm, itemCode, function (is_free_in_so, allowedQty) {
                    if (!is_free_in_so) {
                        frappe.msgprint(__("This item is not marked as free in the Sales Order. Please use the regular scanner."));
                        frm.set_value('custom_scan_barcodes_for_free_items', '');
                        return;
                    }

                    const currentFreeItems = frm.doc.items.filter(item =>
                        item.item_code === itemCode &&
                        item.batch_no === batchNo &&
                        item.is_free_item === 1
                    );

                    const currentTotalQty = currentFreeItems.reduce((total, item) => total + (item.qty || 0), 0);

                    if ((currentTotalQty + 1) > allowedQty) {
                        frappe.msgprint({
                            title: __('Quantity Exceeded'),
                            message: __(`Cannot scan more free items. Current: ${currentTotalQty}, Allowed: ${allowedQty} for item ${itemCode}`),
                            indicator: 'red'
                        });
                        frm.set_value('custom_scan_barcodes_for_free_items', '');
                        return;
                    }

                    frappe.db.get_value('Item', itemCode, 'item_name', function (r) {
                        const itemName = r.item_name;

                        const existingRow = currentFreeItems[0];

                        if (existingRow) {
                            const newQty = existingRow.qty + 1;
                            const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes((existingRow.uom || '').toLowerCase());
                            const newStockQty = isUnitUOM ? newQty : newQty * conversionRate;

                            if (!frm._custom_amounts) frm._custom_amounts = {};
                            frm._custom_amounts[existingRow.name] = 0;

                            Promise.all([
                                frappe.model.set_value(existingRow.doctype, existingRow.name, 'qty', newQty),
                                frappe.model.set_value(existingRow.doctype, existingRow.name, 'stock_qty', newStockQty),
                                frappe.model.set_value(existingRow.doctype, existingRow.name, 'custom_out_qty', newQty),
                                frappe.model.set_value(existingRow.doctype, existingRow.name, 'rate', 0),
                                frappe.model.set_value(existingRow.doctype, existingRow.name, 'amount', 0)
                            ]).then(() => {
                                update_total_qty(frm);
                                calculate_document_totals(frm);
                                // refresh_taxes_on_net_total_change(frm, frm.doc.net_total);
                                frm.set_value('custom_scan_barcodes_for_free_items', '');
                            });
                        } else {
                            const newRow = frm.add_child('items');
                            const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes((uom || '').toLowerCase());
                            const stockQty = isUnitUOM ? 1 : conversionRate;

                            if (!frm._custom_amounts) frm._custom_amounts = {};
                            frm._custom_amounts[newRow.name] = 0;

                            Promise.all([
                                frappe.model.set_value(newRow.doctype, newRow.name, 'item_code', itemCode),
                                frappe.model.set_value(newRow.doctype, newRow.name, 'item_name', itemName),
                                frappe.model.set_value(newRow.doctype, newRow.name, 'qty', 1),
                                frappe.model.set_value(newRow.doctype, newRow.name, 'uom', uom),
                                frappe.model.set_value(newRow.doctype, newRow.name, 'conversion_factor', conversionRate),
                                frappe.model.set_value(newRow.doctype, newRow.name, 'stock_qty', stockQty),
                                frappe.model.set_value(newRow.doctype, newRow.name, 'batch_no', batchNo),
                                frappe.model.set_value(newRow.doctype, newRow.name, 'barcode', barcode),
                                frappe.model.set_value(newRow.doctype, newRow.name, 'custom_out_qty', 1),
                                frappe.model.set_value(newRow.doctype, newRow.name, 'rate', 0),
                                frappe.model.set_value(newRow.doctype, newRow.name, 'amount', 0),
                                frappe.model.set_value(newRow.doctype, newRow.name, 'is_free_item', 1)
                            ]).then(() => {
                                if (expiryDate) {
                                    frappe.model.set_value(newRow.doctype, newRow.name, 'batch_expiry_date', expiryDate);
                                }

                                frm.refresh_field('items');
                                update_total_qty(frm);
                                frm.set_value('custom_scan_barcodes_for_free_items', '');
                            });
                        }
                    });
                });
            }
        });
    },


    // 🔥 VALIDATE - Ensure our custom calculations are preserved
    validate: function (frm) {
        console.log('✅ Validating custom calculations...');

        // Recalculate all amounts based on our UOM logic
        if (frm.doc.items) {
            let total_amount = 0;

            frm.doc.items.forEach((row) => {
                if (!row.is_free_item && row.rate && row.qty) {
                    const uomLower = (row.uom || '').toLowerCase().trim();
                    const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uomLower);

                    let correctAmount;
                    if (isUnitUOM) {
                        // Unit UOM: amount = rate * qty
                        correctAmount = flt(row.rate) * flt(row.qty);
                        console.log(`✅ ${row.item_code} - Unit UOM: ${row.rate} × ${row.qty} = ${correctAmount}`);
                    } else {
                        // Non-Unit UOM: amount = rate * stock_qty
                        correctAmount = flt(row.rate) * flt(row.stock_qty || 0);
                        console.log(`✅ ${row.item_code} - Non-Unit UOM: ${row.rate} × ${row.stock_qty} = ${correctAmount}`);
                    }

                    // Force set the amount
                    row.amount = correctAmount;
                    total_amount += correctAmount;
                } else if (row.is_free_item) {
                    row.amount = 0;
                    row.rate = 0;
                }
            });

            // Update net total
            frm.doc.net_total = total_amount;
            frm.doc.base_net_total = total_amount;

            console.log('✅ Validation complete. Net total:', total_amount);
        }

        // Update total_qty
        update_total_qty(frm);
    }
});

// ✅ Child Table Events
frappe.ui.form.on('Delivery Note Item', {
    qty: function (frm, cdt, cdn) {
        if (frm._updating_from_scan || frm._restoring_amounts || frm._calculating_in_progress) return;

        const row = locals[cdt][cdn];

        // Fix amount based on UOM
        if (!row.is_free_item && !row.custom_is_free_item && row.rate) {
            fix_item_amount(row);
        }

        setTimeout(() => {
            update_total_qty(frm);
            calculate_document_totals(frm);
            frm.script_manager.trigger("calculate_taxes_and_totals");
        }, 100);
    },

    amount: function (frm, cdt, cdn) {
        if (frm._updating_from_scan || frm._force_no_triggers || frm._restoring_amounts || frm._calculating_in_progress) return;

        // Update totals when amount changes
        setTimeout(() => {
            update_total_qty(frm);
            calculate_document_totals(frm);
            frm.script_manager.trigger("calculate_taxes_and_totals");
        }, 100);
    },

    rate: function (frm, cdt, cdn) {
        if (frm._restoring_amounts || frm._calculating_in_progress) return;

        const row = locals[cdt][cdn];

        // Fix amount based on UOM
        if (!row.is_free_item && !row.custom_is_free_item && row.rate) {
            fix_item_amount(row);
        }

        setTimeout(() => {
            calculate_document_totals(frm);
            frm.script_manager.trigger("calculate_taxes_and_totals");
        }, 100);
    },

    is_free_item: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.is_free_item) {
            frappe.model.set_value(cdt, cdn, 'rate', 0);
            frappe.model.set_value(cdt, cdn, 'amount', 0);
        }
        setTimeout(() => {
            update_total_qty(frm);
            calculate_document_totals(frm);
            frm.script_manager.trigger("calculate_taxes_and_totals");
        }, 100);
    },

    stock_qty: function (frm, cdt, cdn) {
        if (frm._updating_from_scan) return;

        const row = locals[cdt][cdn];

        // Fix amount based on UOM
        if (!row.is_free_item && !row.custom_is_free_item && row.rate) {
            fix_item_amount(row);
        }

        setTimeout(() => {
            update_total_qty(frm);
            calculate_document_totals(frm);
            frm.script_manager.trigger("calculate_taxes_and_totals");
        }, 100);
    },

    custom_out_qty: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.custom_out_qty) {
            const uomLower = (row.uom || '').toLowerCase().trim();
            const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uomLower);

            if (isUnitUOM) {
                frappe.model.set_value(cdt, cdn, 'qty', row.custom_out_qty);
            } else {
                const newStockQty = row.custom_out_qty * (row.conversion_factor || 1);
                frappe.model.set_value(cdt, cdn, 'stock_qty', newStockQty);
                frappe.model.set_value(cdt, cdn, 'qty', row.custom_out_qty);
            }
        }
        if (!row.is_free_item && !row.custom_is_free_item && row.rate) {
            fix_item_amount(row);
        }
        setTimeout(() => {
            update_total_qty(frm);
            calculate_document_totals(frm);
            frm.script_manager.trigger("calculate_taxes_and_totals");
        }, 100);
    },

    uom: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        // Fix amount based on UOM
        if (!row.is_free_item && !row.custom_is_free_item && row.rate) {
            fix_item_amount(row);
        }

        setTimeout(() => {
            update_total_qty(frm);
            frm.script_manager.trigger("calculate_taxes_and_totals");
        }, 100);
    },

    items_add: function (frm) {
        setTimeout(() => {
            update_total_qty(frm);
            frm.script_manager.trigger("calculate_taxes_and_totals");
        }, 100);
    },

    items_remove: function (frm) {
        setTimeout(() => {
            update_total_qty(frm);
            frm.script_manager.trigger("calculate_taxes_and_totals");
        }, 100);
    }
});

// ✅ SIMPLE FUNCTION to fix item amount based on UOM
function fix_item_amount(row) {
    if (!row.rate || row.is_free_item || row.custom_is_free_item) {
        return;
    }

    const uomLower = (row.uom || '').toLowerCase().trim();
    const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uomLower);

    let amount;
    if (isUnitUOM) {
        amount = flt(row.rate) * flt(row.qty || 0);
    } else {
        amount = flt(row.rate) * flt(row.stock_qty || 0);
    }

    // Set amount directly
    row.amount = amount;

    console.log(`💰 Fixed amount for ${row.item_code}: ${row.rate} × ${isUnitUOM ? row.qty : row.stock_qty} = ${amount}`);
}

function protect_amount_aggressively(frm, row, correctAmount, callback) {
    console.log('🛡️ Protecting amount for:', row.item_code, 'Expected amount:', correctAmount);

    let protectionCount = 0;
    const maxProtections = 3; // Reduced from 10 to prevent loops

    const protectionLoop = () => {
        if (protectionCount >= maxProtections) {
            console.log('🛡️ Max protection attempts reached for:', row.item_code);
            if (callback) callback();
            return;
        }

        const currentAmount = flt(row.amount);
        if (Math.abs(currentAmount - correctAmount) > 0.01) {
            protectionCount++;
            console.log(`🛡️ Protection attempt ${protectionCount}: Fixing amount ${currentAmount} → ${correctAmount}`);

            // Store in our custom amounts tracker
            if (!frm._custom_amounts) frm._custom_amounts = {};
            frm._custom_amounts[row.name] = correctAmount;

            // Set the amount with setTimeout
            setTimeout(() => {
                row.amount = correctAmount;
                frappe.model.set_value(row.doctype, row.name, 'amount', correctAmount);

                // Continue protection loop after a longer delay
                setTimeout(protectionLoop, 300);
            }, 100);
        } else {
            console.log('✅ Amount protection successful for:', row.item_code, 'Final amount:', currentAmount);
            if (callback) callback();
        }
    };

    // Start protection after short delay
    setTimeout(protectionLoop, 200);
}

function fix_all_amounts(frm) {
    console.log('🔧 Manually fixing all amounts based on UOM logic...');

    if (!frm._custom_amounts) frm._custom_amounts = {};

    if (frm.doc.items) {
        frm.doc.items.forEach((row) => {
            if (!row.is_free_item && row.rate && row.qty) {
                const uomLower = (row.uom || '').toLowerCase().trim();
                const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uomLower);

                let correctAmount;
                if (isUnitUOM) {
                    correctAmount = flt(row.rate) * flt(row.qty);
                    console.log(`🔧 ${row.item_code} - Unit UOM: ${row.rate} * ${row.qty} = ${correctAmount}`);
                } else {
                    correctAmount = flt(row.rate) * flt(row.stock_qty || 0);
                    console.log(`🔧 ${row.item_code} - Non-Unit UOM: ${row.rate} * ${row.stock_qty} = ${correctAmount}`);
                }

                // Store and apply
                frm._custom_amounts[row.name] = correctAmount;
                row.amount = correctAmount;
                frappe.model.set_value(row.doctype, row.name, 'amount', correctAmount);

                // Start aggressive protection
                protect_amount_aggressively(frm, row, correctAmount);
            } else if (row.is_free_item) {
                // Free items should always have 0 amount
                frm._custom_amounts[row.name] = 0;
                row.amount = 0;
                frappe.model.set_value(row.doctype, row.name, 'amount', 0);
            }
        });
    }

    frm.refresh_field('items');
    console.log('🔧 Manual amount fixing completed');
}

function setup_calculate_interceptor(frm) {
    if (frm._calculate_intercepted) return;

    frm._calculate_intercepted = true;

    // Store the original trigger method
    if (!frm._original_trigger) {
        frm._original_trigger = frm.script_manager.trigger.bind(frm.script_manager);
    }

    // Override the script manager's trigger method
    frm.script_manager.trigger = function (event, ...args) {
        if (event === "calculate_taxes_and_totals") {
            // Prevent multiple concurrent calculations to avoid loops
            if (frm._calculating_in_progress) {
                console.log("🚫 Calculation already in progress, skipping to prevent loop...");
                return;
            }

            frm._calculating_in_progress = true;
            console.log("🚫 Intercepting calculate_taxes_and_totals - protecting our amounts");

            // Store our custom amounts before ERPNext calculation
            store_custom_amounts(frm);

            // Call original ERPNext calculation
            const result = frm._original_trigger.call(this, event, ...args);

            // Restore our amounts after ERPNext calculation with delay
            setTimeout(() => {
                restore_custom_amounts(frm);
                // Mark calculation as complete after restoration
                setTimeout(() => {
                    frm._calculating_in_progress = false;
                    console.log("✅ Calculation cycle complete");
                }, 200);
            }, 50);

            return result;
        } else {
            return frm._original_trigger.call(this, event, ...args);
        }
    };

    console.log("✅ Calculate interceptor set up successfully");
}

function store_custom_amounts(frm) {
    try {
        if (!frm._stored_amounts) frm._stored_amounts = {};

        frm.doc.items.forEach((row) => {
            if (row.name) {
                // Calculate correct amount based on UOM
                const uomLower = (row.uom || '').toLowerCase().trim();
                const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uomLower);

                let correctAmount = 0;
                if (row.is_free_item || row.custom_is_free_item) {
                    correctAmount = 0;
                } else if (row.rate) {
                    if (isUnitUOM) {
                        correctAmount = flt(row.rate) * flt(row.qty || 0);
                    } else {
                        correctAmount = flt(row.rate) * flt(row.stock_qty || 0);
                    }
                }

                frm._stored_amounts[row.name] = correctAmount;
                console.log(`📦 Stored amount for ${row.item_code}: ${correctAmount}`);
            }
        });

        // Store totals
        frm._stored_totals = {
            total_qty: frm.doc.total_qty,
            net_total: calculate_net_total_from_items(frm)
        };

    } catch (e) {
        console.error("❌ Error storing custom amounts:", e);
    }
}

function restore_custom_amounts(frm) {
    try {
        if (!frm._stored_amounts) return;

        // Prevent triggering more calculations during restoration
        frm._restoring_amounts = true;
        let needsRefresh = false;

        frm.doc.items.forEach((row) => {
            if (row.name && frm._stored_amounts[row.name] !== undefined) {
                const storedAmount = frm._stored_amounts[row.name];
                const currentAmount = flt(row.amount);

                if (Math.abs(currentAmount - storedAmount) > 0.01) {
                    console.log(`🔄 Restoring amount for ${row.item_code}: ${currentAmount} → ${storedAmount}`);

                    // Use direct assignment to avoid triggering change events
                    row.amount = storedAmount;
                    row.base_amount = storedAmount * (frm.doc.conversion_rate || 1);
                    row.net_amount = storedAmount;
                    row.base_net_amount = storedAmount * (frm.doc.conversion_rate || 1);

                    needsRefresh = true;
                }
            }
        });

        // Restore total_qty
        if (frm._stored_totals && frm._stored_totals.total_qty) {
            if (Math.abs(frm.doc.total_qty - frm._stored_totals.total_qty) > 0.01) {
                console.log(`🔄 Restoring total_qty: ${frm.doc.total_qty} → ${frm._stored_totals.total_qty}`);
                frm.doc.total_qty = frm._stored_totals.total_qty;
                needsRefresh = true;
            }
        }

        // Update document totals silently
        if (frm._stored_totals && frm._stored_totals.net_total) {
            frm.doc.net_total = frm._stored_totals.net_total;
            frm.doc.total = frm._stored_totals.net_total;
            frm.doc.base_net_total = frm._stored_totals.net_total * (frm.doc.conversion_rate || 1);
            frm.doc.base_total = frm._stored_totals.net_total * (frm.doc.conversion_rate || 1);
        }

        if (needsRefresh) {
            // Use setTimeout to avoid immediate retrigger
            setTimeout(() => {
                frm.refresh_field('items');
                frm.refresh_field('total_qty');
                frm.refresh_field('net_total');
                frm.refresh_field('total');

                // Clear the flag after restoration is complete
                setTimeout(() => {
                    frm._restoring_amounts = false;
                    console.log("✅ Custom amounts restored successfully");
                }, 100);
            }, 50);
        } else {
            frm._restoring_amounts = false;
        }

    } catch (e) {
        frm._restoring_amounts = false;
        console.error("❌ Error restoring custom amounts:", e);
    }
}

function calculate_net_total_from_items(frm) {
    let total = 0;
    if (frm.doc.items) {
        frm.doc.items.forEach((row) => {
            if (row && !row.__deleted) {
                total += flt(row.amount || 0);
            }
        });
    }
    return total;
}

// ✅ IMPROVED FREE SCANNER TOGGLE FUNCTION with BOTH field name checks
function check_and_toggle_free_scanner(frm) {
    console.log('🔍 Checking for free scanner visibility...');

    // ✅ PREVENT MULTIPLE CONCURRENT CALLS
    if (frm._checking_free_scanner) {
        console.log('🔒 Free scanner check already in progress, skipping...');
        return;
    }

    frm._checking_free_scanner = true;

    // ✅ ULTRA-AGGRESSIVE SEARCH for Sales Order reference
    let salesOrderRef = null;

    // Method 1: Direct from document
    if (frm.doc.sales_order) {
        salesOrderRef = frm.doc.sales_order;
        console.log('📄 Found Sales Order from doc.sales_order:', salesOrderRef);
    }

    // Method 2: From items table  
    if (!salesOrderRef && frm.doc.items && frm.doc.items.length > 0) {
        for (let item of frm.doc.items) {
            if (item.against_sales_order) {
                salesOrderRef = item.against_sales_order;
                console.log('📄 Found Sales Order from items table:', salesOrderRef);
                break;
            }
        }
    }

    // Method 3: From custom_ref table (CRITICAL!)
    if (!salesOrderRef && frm.doc.custom_ref && frm.doc.custom_ref.length > 0) {
        for (let ref of frm.doc.custom_ref) {
            if (ref.custom_against_sales_order) {
                salesOrderRef = ref.custom_against_sales_order;
                console.log('📄 Found Sales Order from custom_ref table:', salesOrderRef);
                break;
            }
        }
    }

    // Method 4: From URL parameters
    if (!salesOrderRef) {
        const urlParams = new URLSearchParams(window.location.search);
        const fromSO = urlParams.get('sales_order');
        if (fromSO) {
            salesOrderRef = fromSO;
            console.log('📄 Found Sales Order from URL:', salesOrderRef);
        }
    }

    // Method 5: From form field
    if (!salesOrderRef && frm.fields_dict.sales_order && frm.fields_dict.sales_order.value) {
        salesOrderRef = frm.fields_dict.sales_order.value;
        console.log('📄 Found Sales Order from form field:', salesOrderRef);
    }

    console.log('🔍 Final Sales Order Reference:', salesOrderRef);

    if (!salesOrderRef) {
        console.log('❌ No Sales Order reference found - will retry with extended delay');
        frm._checking_free_scanner = false;

        // ✅ EXTENDED RETRY with longer delay
        setTimeout(() => {
            if (!frm._free_scanner_final_check) {
                frm._free_scanner_final_check = true;
                console.log('🔄 Retrying free scanner check after extended delay...');
                check_and_toggle_free_scanner(frm);
            } else {
                console.log('❌ Final check - still no Sales Order, showing manual button');
                add_manual_free_scanner_button(frm);
            }
        }, 5000); // Extended to 5 seconds
        return;
    }

    console.log('🔍 Fetching Sales Order data:', salesOrderRef);

    // ✅ Check Sales Order for free items
    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Sales Order",
            name: salesOrderRef
        },
        callback: function (response) {
            frm._checking_free_scanner = false; // ✅ Reset flag

            console.log('📋 Sales Order response:', response);

            if (response.message && response.message.items) {
                // ✅ FIXED: Check for free items using BOTH field names
                const freeItems = response.message.items.filter(item =>
                    item.is_free_item === 1 || item.custom_is_free_item === 1
                );

                const hasFreeItems = freeItems.length > 0;

                console.log('🔍 Free Items Analysis:', {
                    salesOrder: salesOrderRef,
                    totalItems: response.message.items.length,
                    freeItemsCount: freeItems.length,
                    hasFreeItems: hasFreeItems,
                    freeItems: freeItems.map(i => ({
                        item_code: i.item_code,
                        qty: i.qty,
                        is_free_item: i.is_free_item,
                        custom_is_free_item: i.custom_is_free_item
                    }))
                });

                // ✅ AGGRESSIVE SHOW/HIDE the scanner
                if (hasFreeItems) {
                    console.log('✅ SHOWING FREE SCANNER - Found', freeItems.length, 'free items');

                    // ✅ FORCE VISIBILITY with multiple methods
                    setTimeout(() => {
                        frm.toggle_display('custom_scan_barcodes_for_free_items', true);
                        frm.set_df_property('custom_scan_barcodes_for_free_items', 'hidden', 0);
                        frm.set_df_property('custom_scan_barcodes_for_free_items', 'read_only', 0);
                        frm.set_df_property('custom_scan_barcodes_for_free_items', 'description',
                            `🎁 Free Item Scanner (${freeItems.length} free items available)`);
                        frm.refresh_field('custom_scan_barcodes_for_free_items');

                        // ✅ TRIPLE-CHECK after delay
                        setTimeout(() => {
                            if (frm.fields_dict.custom_scan_barcodes_for_free_items &&
                                !frm.fields_dict.custom_scan_barcodes_for_free_items.$wrapper.is(':visible')) {
                                console.log('🔄 Free scanner STILL hidden, using emergency show...');
                                frm.fields_dict.custom_scan_barcodes_for_free_items.$wrapper.show();
                                frm.refresh_field('custom_scan_barcodes_for_free_items');
                            }
                        }, 1000);
                    }, 100);

                } else {
                    console.log('❌ HIDING FREE SCANNER - No free items found');
                    frm.toggle_display('custom_scan_barcodes_for_free_items', false);
                    frm.set_df_property('custom_scan_barcodes_for_free_items', 'hidden', 1);
                }
            } else {
                console.log('❌ No Sales Order items found, hiding free scanner');
                frm.toggle_display('custom_scan_barcodes_for_free_items', false);
            }
        },
        error: function (err) {
            frm._checking_free_scanner = false; // ✅ Reset flag
            console.error('❌ Error fetching Sales Order:', err);
            frm.toggle_display('custom_scan_barcodes_for_free_items', false);
        }
    });
}

// ✅ MANUAL BUTTON as backup
function add_manual_free_scanner_button(frm) {
    frm.add_custom_button(__('Show Free Scanner'), function () {
        frm.toggle_display('custom_scan_barcodes_for_free_items', true);
        frm.set_df_property('custom_scan_barcodes_for_free_items', 'hidden', 0);
        frm.set_df_property('custom_scan_barcodes_for_free_items', 'description',
            '🎁 Free Item Scanner (Manual Override)');
        frm.refresh_field('custom_scan_barcodes_for_free_items');
        frappe.msgprint(__('Free item scanner is now visible.'));
    }, __('Scanner'));
}

// ✅ IMPROVED free item check with BOTH field names
function check_if_item_is_free_in_sales_order(frm, itemCode, callback) {
    // ✅ Use same aggressive SO detection
    let salesOrderToCheck = null;

    if (frm.doc.sales_order) {
        salesOrderToCheck = frm.doc.sales_order;
    } else if (frm.doc.items && frm.doc.items.length > 0) {
        for (let item of frm.doc.items) {
            if (item.against_sales_order) {
                salesOrderToCheck = item.against_sales_order;
                break;
            }
        }
    } else if (frm.doc.custom_ref && frm.doc.custom_ref.length > 0) {
        for (let ref of frm.doc.custom_ref) {
            if (ref.custom_against_sales_order) {
                salesOrderToCheck = ref.custom_against_sales_order;
                break;
            }
        }
    }

    if (!salesOrderToCheck) {
        callback(false, 0);
        return;
    }

    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Sales Order",
            name: salesOrderToCheck
        },
        callback: function (response) {
            if (response.message && response.message.items) {
                // ✅ FIXED: Check for free items using BOTH field names
                const freeItem = response.message.items.find(item =>
                    item.item_code === itemCode && (item.is_free_item === 1 || item.custom_is_free_item === 1)
                );
                callback(!!freeItem, freeItem ? freeItem.qty : 0);
            } else {
                callback(false, 0);
            }
        }
    });
}

// ✅ 🔥 FIXED total quantity calculation with SIMPLER LOGIC and PROPER DELAYS
function update_total_qty(frm) {
    if (frm._updating_total) return; // Prevent recursive calls

    frm._updating_total = true;

    // Use setTimeout to ensure DOM is ready and avoid conflicts
    setTimeout(() => {
        let unitTotal = 0;    // Total of qty fields for Unit UOM items
        let nonUnitTotal = 0; // Total of stock_qty fields for Non-Unit UOM items

        console.log('📊 =============== CALCULATING TOTAL QUANTITY ===============');

        if (frm.doc.items && frm.doc.items.length > 0) {
            frm.doc.items.forEach((row, index) => {
                // Skip deleted rows or rows without item_code
                if (!row || !row.item_code || row.__deleted) return;

                const uom = (row.uom || '').toLowerCase().trim();
                const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uom);

                if (isUnitUOM) {
                    const qtyValue = flt(row.qty || 0);
                    unitTotal += qtyValue;
                    console.log(`📦 Row ${index + 1}: ${row.item_code} - Unit UOM - qty: ${qtyValue}`);
                } else {
                    const stockQtyValue = flt(row.stock_qty || 0);
                    nonUnitTotal += stockQtyValue;
                    console.log(`📦 Row ${index + 1}: ${row.item_code} - Non-Unit UOM - stock_qty: ${stockQtyValue}`);
                }
            });
        }

        // ✅ 🔥 NEW LOGIC: Use unitTotal if we have any Unit UOM items, otherwise use nonUnitTotal
        let finalTotal;
        if (unitTotal > 0) {
            finalTotal = unitTotal;
            console.log('📊 Using UNIT TOTAL (has Unit UOM items):', finalTotal);
        } else {
            finalTotal = nonUnitTotal;
            console.log('📊 Using NON-UNIT TOTAL (no Unit UOM items):', finalTotal);
        }

        // ✅ UPDATE with proper setTimeout delays for reliability
        if (Math.abs(frm.doc.total_qty - finalTotal) > 0.01) {
            console.log('📊 Updating total_qty from', frm.doc.total_qty, 'to', finalTotal);
            frm.doc.total_qty = finalTotal;

            // First set the value
            setTimeout(() => {
                frm.set_value('total_qty', finalTotal);

                // Then refresh the field after value is set
                setTimeout(() => {
                    frm.refresh_field('total_qty');

                    // Mark update as complete
                    setTimeout(() => {
                        frm._updating_total = false;
                        console.log('✅ Total qty update complete:', finalTotal);
                    }, 50);
                }, 100);
            }, 50);
        } else {
            frm._updating_total = false;
        }
    }, 100);
}

// ✅ SIMPLE FUNCTION to fix item amount based on UOM
function fix_item_amount(row) {
    if (!row.rate || row.is_free_item || row.custom_is_free_item) {
        return;
    }

    const uomLower = (row.uom || '').toLowerCase().trim();
    const isUnitUOM = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uomLower);

    let amount;
    if (isUnitUOM) {
        amount = flt(row.rate) * flt(row.qty || 0);
    } else {
        amount = flt(row.rate) * flt(row.stock_qty || 0);
    }

    // Set amount directly
    row.amount = amount;

    console.log(`💰 Fixed amount for ${row.item_code}: ${row.rate} × ${isUnitUOM ? row.qty : row.stock_qty} = ${amount}`);
}

// ✅ FUNCTION to calculate document totals from items
function calculate_document_totals(frm) {
    if (!frm.doc.items || frm._calculating_totals || frm._calculating_in_progress || frm._restoring_amounts || frm._tax_calculation_in_progress) return;

    // PREVENT MULTIPLE CONCURRENT CALCULATIONS
    if (frm._last_calculation_time && (Date.now() - frm._last_calculation_time) < 2000) {
        console.log('🚫 Skipping calculation - too soon after last one');
        return;
    }

    frm._calculating_totals = true;
    frm._last_calculation_time = Date.now();

    setTimeout(() => {
        let net_total = 0;

        console.log('💰 =============== CALCULATING DOCUMENT TOTALS ===============');

        frm.doc.items.forEach((row, index) => {
            if (!row || row.__deleted) return;

            const amount = flt(row.amount || 0);
            net_total += amount;

            console.log(`💰 Row ${index + 1}: ${row.item_code} - Amount: ${amount}`);
        });

        console.log('💰 Total calculated from items:', net_total);

        // Store the old net_total to check if it changed
        const old_net_total = frm.doc.net_total;

        // ALWAYS update document totals to match item amounts
        console.log('💰 Updating net_total from', frm.doc.net_total, 'to', net_total);

        frm.doc.net_total = net_total;
        frm.doc.total = net_total;  // Total should equal net_total
        frm.doc.base_net_total = net_total * (frm.doc.conversion_rate || 1);
        frm.doc.base_total = net_total * (frm.doc.conversion_rate || 1);

        // Force set values using frm.set_value for better reliability
        setTimeout(() => {
            frm.set_value('net_total', net_total);
            frm.set_value('total', net_total);  // Force total = net_total
            frm.set_value('base_net_total', net_total * (frm.doc.conversion_rate || 1));
            frm.set_value('base_total', net_total * (frm.doc.conversion_rate || 1));

            setTimeout(() => {
                frm.refresh_field('net_total');
                frm.refresh_field('total');
                frm.refresh_field('base_net_total');
                frm.refresh_field('base_total');

                // 🔥 REFRESH TAXES when net_total changes
                if (Math.abs(old_net_total - net_total) > 0.01) {
                    console.log('🔄 Net total changed, recalculating taxes...');
                    // refresh_taxes_on_net_total_change(frm, net_total);
                }

                setTimeout(() => {
                    frm._calculating_totals = false;
                    console.log('✅ Document totals update complete - Total now equals:', net_total);
                }, 50);
            }, 100);
        }, 50);
    }, 100);
}

// 🔥 FUNCTION to refresh taxes when net_total changes with UOM-based calculation
function refresh_taxes_on_net_total_change(frm, correct_net_total) {
    if (!frm.doc.taxes || frm.doc.taxes.length === 0) {
        console.log('❌ No taxes to refresh');
        return;
    }

    // PREVENT MULTIPLE CONCURRENT TAX CALCULATIONS
    if (frm._tax_calculation_in_progress) {
        console.log('🚫 Tax calculation already in progress, skipping...');
        return;
    }

    frm._tax_calculation_in_progress = true;
    console.log('🔄 Refreshing taxes with UOM-based calculation...');

    // Calculate tax base amount using UOM logic for each item
    let total_taxable_amount = 0;

    frm.doc.items.forEach((item, index) => {
        if (!item || item.__deleted || item.is_free_item) return;

        const uom_lower = (item.uom || '').toLowerCase().trim();
        const is_unit_uom = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uom_lower);

        let item_taxable_amount;
        if (is_unit_uom) {
            // Unit UOM: use qty × rate
            item_taxable_amount = flt(item.qty || 0) * flt(item.rate || 0);
            console.log(`📊 Item ${index + 1} (${item.item_code}) - Unit UOM: ${item.qty} × ${item.rate} = ${item_taxable_amount}`);
        } else {
            // Non-Unit UOM (Box/Carton): use stock_qty × rate
            item_taxable_amount = flt(item.stock_qty || 0) * flt(item.rate || 0);
            console.log(`📊 Item ${index + 1} (${item.item_code}) - Non-Unit UOM: ${item.stock_qty} × ${item.rate} = ${item_taxable_amount}`);
        }

        total_taxable_amount += item_taxable_amount;
    });

    console.log(`💰 Total taxable amount (UOM-based): ${total_taxable_amount}`);

    // Recalculate each tax row using UOM-based taxable amount WITH TIMEOUTS
    let cumulative_total = total_taxable_amount;

    setTimeout(() => {
        frm.doc.taxes.forEach((tax, index) => {
            if (tax.charge_type === "On Net Total") {
                const old_tax_amount = tax.tax_amount;

                // Calculate tax on UOM-based taxable amount
                const new_tax_amount = flt(total_taxable_amount * flt(tax.rate) / 100);
                const new_base_tax_amount = flt(new_tax_amount * (frm.doc.conversion_rate || 1));

                // Update cumulative total
                cumulative_total += new_tax_amount;
                const new_total = cumulative_total;
                const new_base_total = flt(new_total * (frm.doc.conversion_rate || 1));

                console.log(`💰 Tax ${index + 1}: ${tax.description} = ${total_taxable_amount} × ${tax.rate}% = ${new_tax_amount} (was: ${old_tax_amount})`);

                // FORCE SET WITH TIMEOUTS
                setTimeout(() => {
                    tax.tax_amount = new_tax_amount;
                    tax.base_tax_amount = new_base_tax_amount;
                    tax.total = new_total;
                    tax.base_total = new_base_total;

                    // FORCE UPDATE VIA FRAPPE WITH TIMEOUT
                    setTimeout(() => {
                        frappe.model.set_value(tax.doctype, tax.name, 'tax_amount', new_tax_amount);

                        setTimeout(() => {
                            frappe.model.set_value(tax.doctype, tax.name, 'total', new_total);

                            // TRIPLE CHECK
                            setTimeout(() => {
                                tax.tax_amount = new_tax_amount;
                                tax.total = new_total;
                                console.log(`🔥 TIMEOUT FORCED Tax ${index + 1}: ${new_tax_amount}`);
                            }, 100);
                        }, 100);
                    }, 100);
                }, 50 * index); // Stagger each tax row
            }
        });
    }, 100);

    // Update document totals to match UOM-based calculation WITH MULTIPLE TIMEOUTS
    setTimeout(() => {
        frm.doc.net_total = total_taxable_amount;
        frm.doc.total = total_taxable_amount;
        frm.doc.base_net_total = flt(total_taxable_amount * (frm.doc.conversion_rate || 1));
        frm.doc.base_total = flt(total_taxable_amount * (frm.doc.conversion_rate || 1));

        setTimeout(() => {
            frm.set_value('net_total', total_taxable_amount);
            frm.set_value('total', total_taxable_amount);

            setTimeout(() => {
                // UPDATE GRAND TOTAL AFTER TAX CALCULATIONS
                const final_grand_total = cumulative_total;
                frm.doc.grand_total = final_grand_total;
                frm.doc.base_grand_total = flt(final_grand_total * (frm.doc.conversion_rate || 1));

                setTimeout(() => {
                    frm.set_value('grand_total', final_grand_total);

                    console.log(`🔄 TIMEOUT Updated totals - Net: ${total_taxable_amount}, Grand: ${final_grand_total}`);
                }, 200);
            }, 300);
        }, 200);
    }, 300);

    // Refresh all relevant fields WITH AGGRESSIVE TIMEOUTS
    setTimeout(() => {
        frm.refresh_field('net_total');
        frm.refresh_field('total');

        setTimeout(() => {
            frm.refresh_field('taxes');

            setTimeout(() => {
                frm.refresh_field('grand_total');
                frm.refresh_field('base_grand_total');

                setTimeout(() => {
                    // FORCE REFRESH TAXES AGAIN
                    frm.refresh_field('taxes');

                    setTimeout(() => {
                        // CLEAR THE TAX CALCULATION FLAG
                        frm._tax_calculation_in_progress = false;
                        console.log('✅ UOM-based taxes TIMEOUT refreshed successfully');
                    }, 200);
                }, 200);
            }, 200);
        }, 200);
    }, 500);
}

// 🔥🔥 SUPER AGGRESSIVE FUNCTION - FORCE FIX EVERYTHING
function force_fix_everything(frm) {
    console.log('🔥🔥 FORCE FIXING EVERYTHING - AGGRESSIVE MODE');

    // STEP 1: FORCE FIX ITEM AMOUNTS BASED ON UOM
    let correct_net_total = 0;

    frm.doc.items.forEach((item, index) => {
        if (!item || item.__deleted || item.is_free_item) return;

        const uom_lower = (item.uom || '').toLowerCase().trim();
        const is_unit_uom = ['unit', 'units', 'nos', 'pcs', 'piece', 'pieces', 'each'].includes(uom_lower);

        let correct_amount;
        if (is_unit_uom) {
            correct_amount = flt(item.qty || 0) * flt(item.rate || 0);
            console.log(`🔥 FORCE Item ${index + 1} (${item.item_code}) - Unit UOM: ${item.qty} × ${item.rate} = ${correct_amount}`);
        } else {
            correct_amount = flt(item.stock_qty || 0) * flt(item.rate || 0);
            console.log(`🔥 FORCE Item ${index + 1} (${item.item_code}) - Non-Unit UOM: ${item.stock_qty} × ${item.rate} = ${correct_amount}`);
        }

        // FORCE SET ITEM AMOUNT WITH MULTIPLE METHODS
        item.amount = correct_amount;
        item.base_amount = correct_amount * (frm.doc.conversion_rate || 1);
        item.net_amount = correct_amount;
        item.base_net_amount = correct_amount * (frm.doc.conversion_rate || 1);

        // FORCE UPDATE VIA FRAPPE
        frappe.model.set_value(item.doctype, item.name, 'amount', correct_amount);

        correct_net_total += correct_amount;
    });

    console.log(`🔥 FORCE Net Total: ${correct_net_total}`);

    // STEP 2: FORCE SET DOCUMENT TOTALS
    frm.doc.net_total = correct_net_total;
    frm.doc.total = correct_net_total;
    frm.doc.base_net_total = correct_net_total * (frm.doc.conversion_rate || 1);
    frm.doc.base_total = correct_net_total * (frm.doc.conversion_rate || 1);

    // FORCE SET VIA FRAPPE
    frm.set_value('net_total', correct_net_total);
    frm.set_value('total', correct_net_total);

    // STEP 3: FORCE CALCULATE AND SET TAXES WITH AGGRESSIVE TIMEOUTS
    if (frm.doc.taxes && frm.doc.taxes.length > 0) {
        setTimeout(() => {
            let cumulative_total = correct_net_total;

            frm.doc.taxes.forEach((tax, index) => {
                if (tax.charge_type === "On Net Total") {
                    // FORCE CALCULATE TAX
                    const correct_tax_amount = flt(correct_net_total * flt(tax.rate) / 100);
                    const correct_base_tax_amount = correct_tax_amount * (frm.doc.conversion_rate || 1);

                    cumulative_total += correct_tax_amount;
                    const correct_total = cumulative_total;
                    const correct_base_total = correct_total * (frm.doc.conversion_rate || 1);

                    console.log(`🔥 FORCE Tax ${index + 1}: ${tax.description} = ${correct_net_total} × ${tax.rate}% = ${correct_tax_amount}`);

                    // FORCE SET TAX VALUES WITH MULTIPLE METHODS
                    tax.tax_amount = correct_tax_amount;
                    tax.base_tax_amount = correct_base_tax_amount;
                    tax.total = correct_total;
                    tax.base_total = correct_base_total;

                    // FORCE UPDATE VIA FRAPPE WITH TIMEOUT
                    setTimeout(() => {
                        frappe.model.set_value(tax.doctype, tax.name, 'tax_amount', correct_tax_amount);

                        setTimeout(() => {
                            frappe.model.set_value(tax.doctype, tax.name, 'total', correct_total);

                            // TRIPLE CHECK - FORCE AGAIN
                            setTimeout(() => {
                                tax.tax_amount = correct_tax_amount;
                                tax.total = correct_total;
                                console.log(`🔥 TRIPLE FORCED Tax ${index + 1}: ${correct_tax_amount}`);
                            }, 100);
                        }, 100);
                    }, 100);
                }
            });

            // STEP 4: FORCE SET GRAND TOTAL WITH MULTIPLE TIMEOUTS
            setTimeout(() => {
                frm.doc.grand_total = cumulative_total;
                frm.doc.base_grand_total = cumulative_total * (frm.doc.conversion_rate || 1);

                setTimeout(() => {
                    frm.set_value('grand_total', cumulative_total);

                    setTimeout(() => {
                        // TRIPLE CHECK GRAND TOTAL
                        frm.doc.grand_total = cumulative_total;
                        console.log(`🔥 TRIPLE FORCED Grand Total: ${cumulative_total}`);
                    }, 150);
                }, 100);
            }, 200);

        }, 150);
    }

    // STEP 5: FORCE REFRESH ALL FIELDS
    setTimeout(() => {
        frm.refresh_field('items');
        frm.refresh_field('net_total');
        frm.refresh_field('total');
        frm.refresh_field('taxes');
        frm.refresh_field('grand_total');

        // DOUBLE FORCE REFRESH AFTER DELAY
        setTimeout(() => {
            frm.refresh_field('items');
            frm.refresh_field('taxes');
            console.log('🔥🔥 FORCE FIX COMPLETE - ALL VALUES FORCED!');
        }, 200);
    }, 100);
}