frappe.ui.form.on('Purchase Receipt', {
    // validate(frm) {
    //     fetchBaseAmountFromInvoice(frm);
    // },
    // onload: function (frm) {
    //     setTimeout(function () {
    //         fetch_invoice_data_for_items(frm);
    //     }, 500); // 500ms delay
    // },
    received_stock_qty: function (frm) {
        update_total_qty(frm);

        // Add manual trigger button
        // frm.add_custom_button("Recalculate Total Qty", () => {
        //     update_total_qty(frm);
        // });

        console.log("✅ Custom Purchase Receipt Client Script loaded");
    },
    base_amount: function (frm) {
        // update_total_amount(frm)

        // Add manual trigger button
        // frm.add_custom_button("Recalculate Total Qty", () => {
        //     update_total_qty(frm);
        // });

        console.log("✅ Custom Purchase Receipt Client Script loaded");
    },

    items_on_form_rendered: function (frm) {
        update_total_qty(frm);
        // update_total_amount(frm)
    },

    scan_barcode: function (frm) {
        if (!frm.doc.scan_barcode) return;

        const barcode = frm.doc.scan_barcode;
        const qty = 1; // Default to 1 per scan; can be enhanced to prompt/input later

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
                            received_stock_qty: qty * conversionRate
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

                        // Fetch all price fields from invoice if present
                        if (uom && frm.doc.custom_purchase_invoice_name) {
                            frappe.db.get_doc('Purchase Invoice', frm.doc.custom_purchase_invoice_name).then(pinv => {
                                if (pinv && pinv.items) {
                                    // Match by item_code, qty, and batch_no if available
                                    let matched_item = pinv.items.find(pi_item =>
                                        pi_item.item_code === itemCode &&
                                        pi_item.qty === qty &&
                                        (pi_item.batch_no ? pi_item.batch_no === batchNo : true)
                                    );
                                    if (matched_item) {
                                        frappe.model.set_value(newRow.doctype, newRow.name, 'base_rate', matched_item.base_rate);
                                        frappe.model.set_value(newRow.doctype, newRow.name, 'price_list_rate', matched_item.price_list_rate || 0);
                                        frappe.model.set_value(newRow.doctype, newRow.name, 'base_price_list_rate', matched_item.base_price_list_rate || 0);
                                        if (uom === 'Unit') {
                                            frappe.model.set_value(newRow.doctype, newRow.name, 'base_amount', matched_item.base_rate * qty);
                                            frappe.model.set_value(newRow.doctype, newRow.name, 'stock_uom_rate', matched_item.stock_uom_rate);
                                            frappe.model.set_value(newRow.doctype, newRow.name, 'net_rate', matched_item.net_rate);
                                            frappe.model.set_value(newRow.doctype, newRow.name, 'net_amount', matched_item.net_amount);
                                            frappe.model.set_value(newRow.doctype, newRow.name, 'base_net_rate', matched_item.base_net_rate);
                                            frappe.model.set_value(newRow.doctype, newRow.name, 'base_net_amount', matched_item.base_net_amount);
                                        } else {
                                            frappe.model.set_value(newRow.doctype, newRow.name, 'base_amount', matched_item.base_amount);
                                            frappe.model.set_value(newRow.doctype, newRow.name, 'stock_uom_rate', matched_item.stock_uom_rate);
                                            frappe.model.set_value(newRow.doctype, newRow.name, 'net_rate', matched_item.net_rate);
                                            frappe.model.set_value(newRow.doctype, newRow.name, 'net_amount', matched_item.net_amount);
                                            frappe.model.set_value(newRow.doctype, newRow.name, 'base_net_rate', matched_item.base_net_rate);
                                            frappe.model.set_value(newRow.doctype, newRow.name, 'base_net_amount', matched_item.base_net_amount);
                                        }
                                        frappe.model.set_value(newRow.doctype, newRow.name, 'purchase_invoice_item', matched_item.name);
                                        return;
                                    }
                                }
                            });
                        }

                        // Fetch and set purchase order, invoice, warehouse, price, etc.
                        update_purchase_order_and_purchase_invoice_fields(frm);
                        fetch_invoice_data_for_items(frm);
                        update_total_amount(frm);
                        update_total_qty(frm);

                        frm.refresh_field('items');
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

    // You might also want to catch any manual row addition
    items_add: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (frm.doc.custom_purchase_order_name) {
            frappe.model.set_value(cdt, cdn, 'purchase_order', frm.doc.custom_purchase_order_name);
        }
    },

    refresh: function (frm) {
        // Add a flag to prevent infinite refresh
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
            // Reset the flag after the logic is executed
            frm.doc.__is_refreshing = false;
        }, 200);

        // Add custom button if needed
        // frm.add_custom_button(__('Fetch Base Amount'), function () {
        //     fetchBaseAmount(frm);
        // });
        // Make form read-only after submit
        if (frm.doc.docstatus === 1) {
            frm.set_read_only();
        }
    },

    // before_save: function (frm) {
    //     update_total_qty(frm);

    //     // Add manual trigger button
    //     // frm.add_custom_button("Recalculate Total Qty", () => {
    //     //     update_total_qty(frm);
    //     // });

    //     console.log("✅ Before Save Custom Purchase Receipt Client Script loaded");
    // },

    // custom_purchase_invoice_name: function (frm) {
    //     if (frm.doc.custom_purchase_invoice_name) {
    //         frappe.db.get_doc('Purchase Invoice', frm.doc.custom_purchase_invoice_name).then(pinv => {
    //             if (pinv && pinv.custom_is_landed_cost) {
    //                 frm.set_value('custom_shipment_order_name', pinv.custom_shipment_name_ref || '');
    //             }
    //         });
    //     }
    // },

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

frappe.ui.form.on('Purchase Receipt Item', {
    received_stock_qty: function (frm, cdt, cdn) {
        update_total_qty(frm);
    },

    items_add: function (frm, cdt, cdn) {
        setTimeout(function () {
            fetch_invoice_data_for_items(frm);
            update_purchase_order_and_purchase_invoice_fields(frm);
        }, 500);
    },

    items_remove: function (frm) {
        update_total_qty(frm);
        setTimeout(function () {
            fetch_invoice_data_for_items(frm);
        }, 500);
    },

    uom: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.uom && frm.doc.custom_purchase_invoice_name) {
            frappe.db.get_doc('Purchase Invoice', frm.doc.custom_purchase_invoice_name).then(pinv => {
                if (pinv && pinv.items) {
                    let matched_item = pinv.items.find(pi_item => pi_item.item_code === row.item_code);
                    if (matched_item) {
                        frappe.model.set_value(cdt, cdn, 'base_rate', matched_item.base_rate);
                        frappe.model.set_value(cdt, cdn, 'price_list_rate', matched_item.price_list_rate || 0);
                        frappe.model.set_value(cdt, cdn, 'base_price_list_rate', matched_item.base_price_list_rate || 0);
                        if (row.uom === 'Unit') {
                            frappe.model.set_value(cdt, cdn, 'base_amount', matched_item.base_rate * row.qty);
                            frappe.model.set_value(cdt, cdn, 'received_stock_qty', row.qty * (row.conversion_factor || 1));
                        } else {
                            frappe.model.set_value(cdt, cdn, 'base_amount', matched_item.base_amount);
                            frappe.model.set_value(cdt, cdn, 'received_stock_qty', matched_item.qty * (row.conversion_factor || 1));
                        }
                        frappe.model.set_value(cdt, cdn, 'stock_uom_rate', matched_item.stock_uom_rate);
                        frappe.model.set_value(cdt, cdn, 'net_rate', matched_item.net_rate);
                        frappe.model.set_value(cdt, cdn, 'net_amount', matched_item.net_amount);
                        frappe.model.set_value(cdt, cdn, 'base_net_rate', matched_item.base_net_rate);
                        frappe.model.set_value(cdt, cdn, 'base_net_amount', matched_item.base_net_amount);
                        frappe.model.set_value(cdt, cdn, 'purchase_invoice_item', matched_item.name);
                        return;
                    }
                }
            });
        }
        setTimeout(function () {
            fetch_invoice_data_for_items(frm);
        }, 500);
    },

    qty: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.uom && frm.doc.custom_purchase_invoice_name) {
            frappe.db.get_doc('Purchase Invoice', frm.doc.custom_purchase_invoice_name).then(pinv => {
                if (pinv && pinv.items) {
                    let matched_item = pinv.items.find(pi_item => pi_item.item_code === row.item_code);
                    if (matched_item) {
                        frappe.model.set_value(cdt, cdn, 'base_rate', matched_item.base_rate);
                        frappe.model.set_value(cdt, cdn, 'price_list_rate', matched_item.price_list_rate || 0);
                        frappe.model.set_value(cdt, cdn, 'base_price_list_rate', matched_item.base_price_list_rate || 0);
                        if (row.uom === 'Unit') {
                            frappe.model.set_value(cdt, cdn, 'base_amount', matched_item.base_rate * row.qty);
                            frappe.model.set_value(cdt, cdn, 'received_stock_qty', row.qty * (row.conversion_factor || 1));
                        } else {
                            frappe.model.set_value(cdt, cdn, 'base_amount', matched_item.base_amount);
                            frappe.model.set_value(cdt, cdn, 'received_stock_qty', matched_item.qty * (row.conversion_factor || 1));
                        }
                        frappe.model.set_value(cdt, cdn, 'stock_uom_rate', matched_item.stock_uom_rate);
                        frappe.model.set_value(cdt, cdn, 'net_rate', matched_item.net_rate);
                        frappe.model.set_value(cdt, cdn, 'net_amount', matched_item.net_amount);
                        frappe.model.set_value(cdt, cdn, 'base_net_rate', matched_item.base_net_rate);
                        frappe.model.set_value(cdt, cdn, 'base_net_amount', matched_item.base_net_amount);
                        frappe.model.set_value(cdt, cdn, 'purchase_invoice_item', matched_item.name);
                        return;
                    }
                }
            });
        }
        update_total_qty(frm);
        setTimeout(function () {
            fetch_invoice_data_for_items(frm);
        }, 500);
    },

    base_rate: function (frm, cdt, cdn) {
        // No local calculation for base_amount here
    },

    item_code: function (frm, cdt, cdn) {
        fetch_invoice_data_for_items(frm);
    },

    // Add handler for barcode field
    'items.barcode': function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.barcode && frm.barcode_batch_map && frm.barcode_batch_map[row.barcode]) {
            const batchNo = frm.barcode_batch_map[row.barcode];
            frappe.model.set_value(cdt, cdn, 'batch_no', batchNo);
            // Remove from map after setting to prevent memory leaks
            delete frm.barcode_batch_map[row.barcode];
        }
    }
});

function update_total_qty(frm) {
    // Always update, even if submitted, to match backend logic
    let all_unit = (frm.doc.items || []).every(item => item.uom === "Unit");
    let total = 0;
    if (all_unit) {
        (frm.doc.items || []).forEach(item => {
            total += flt(item.qty);
        });
    } else {
        (frm.doc.items || []).forEach(item => {
            total += flt(item.received_stock_qty);
        });
    }
    frm.set_value("total_qty", total);
    frm.refresh_field("total_qty");
}

function update_total_amount(frm) {
    if (frm.doc.custom_purchase_invoice_name) return; // Invoice present, totals come from invoice
    if (frm.doc.docstatus === 1) return;
    let total = 0;
    (frm.doc.items || []).forEach(item => {
        total += flt(item.base_amount);
    });
    frm.set_value("base_total", total);
    frm.refresh_field("base_total");
}

function fetchingValueOfStockRateUom(frm, cdt, cdn) {
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint(__("No items found in the table."));
        return;
    }

    setTimeout(() => {
        frm.doc.items.forEach(item => {
            if (item.purchase_invoice) {
                frappe.db.get_doc("Purchase Invoice", item.purchase_invoice).then(purchase_invoice => {
                    console.log("📄 Fetched Purchase Invoice:", purchase_invoice);
                    if (purchase_invoice && purchase_invoice.items) {
                        // Find matching item by item_code
                        let matched_item = purchase_invoice.items.find(pi_item => pi_item.item_code === item.item_code);

                        if (matched_item) {
                            frappe.model.set_value(item.doctype, item.name, "stock_uom_rate", matched_item.rate);
                            frappe.model.set_value(item.doctype, item.name, "base_amount", item.base_rate * item.stock_uom_rate);

                        }
                    }
                });
            }
        });
    }, 1000);
}

function fetchBaseAmountFromInvoiceOnly(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!frm.doc.custom_purchase_invoice_name || !row.item_code) return;
    frappe.db.get_doc('Purchase Invoice', frm.doc.custom_purchase_invoice_name).then(pinv => {
        if (pinv && pinv.items) {
            let matched_item = pinv.items.find(pi_item => pi_item.item_code === row.item_code);
            if (matched_item) {
                frappe.model.set_value(cdt, cdn, 'base_amount', matched_item.base_amount);
            } else {
                frappe.msgprint(__('No matching item in the selected Purchase Invoice for item: ' + row.item_code));
            }
        }
    });
}

function fetchBaseAmount(frm, cdt, cdn) {
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint(__("No items found in the table."));
        return;
    }

    setTimeout(() => {
        frm.doc.items.forEach(item => {
            if (item.purchase_invoice) {
                frappe.db.get_doc("Purchase Invoice", item.purchase_invoice).then(purchase_invoice => {
                    console.log("📄 Fetched Purchase Invoice:", purchase_invoice);
                    if (purchase_invoice && purchase_invoice.items) {
                        // Find matching item by item_code
                        let matched_item = purchase_invoice.items.find(pi_item => pi_item.item_code === item.item_code);

                        if (matched_item) {
                            frappe.model.set_value(item.doctype, item.name, "base_amount", matched_item.base_amount);

                            // Update total if needed
                            let total = 0;
                            frm.doc.items.forEach(row => {
                                total += (row.base_amount || 0);
                            });
                            frm.set_value('base_total', total);
                        }
                    }
                });
            }
        });
    }, 1000);
}

function fetch_invoice_data_for_items(frm) {
    if (!frm.doc.custom_purchase_invoice_name) {
        frappe.msgprint(__('Please select a Purchase Invoice first.'));
        return;
    }
    console.log("Trying to fetch Purchase Invoice:", frm.doc.custom_purchase_invoice_name);
    frappe.db.get_doc('Purchase Invoice', frm.doc.custom_purchase_invoice_name).then(pinv => {
        if (pinv && pinv.items && pinv.items.length) {
            frm.doc.items.forEach(item => {
                let matched = pinv.items.find(pi_item => pi_item.item_code === item.item_code);
                if (matched) {
                    frappe.model.set_value(item.doctype, item.name, 'base_rate', matched.base_rate);
                    frappe.model.set_value(item.doctype, item.name, 'price_list_rate', matched.price_list_rate || 0);
                    frappe.model.set_value(item.doctype, item.name, 'base_price_list_rate', matched.base_price_list_rate || 0);
                    if (item.uom === 'Unit') {
                        frappe.model.set_value(item.doctype, item.name, 'base_amount', matched.base_rate * item.qty);
                    } else {
                        frappe.model.set_value(item.doctype, item.name, 'base_amount', matched.base_amount);
                    }
                    frappe.model.set_value(item.doctype, item.name, 'stock_uom_rate', matched.stock_uom_rate);
                    frappe.model.set_value(item.doctype, item.name, 'net_rate', matched.net_rate);
                    frappe.model.set_value(item.doctype, item.name, 'net_amount', matched.net_amount);
                    frappe.model.set_value(item.doctype, item.name, 'base_net_rate', matched.base_net_rate);
                    frappe.model.set_value(item.doctype, item.name, 'base_net_amount', matched.base_net_amount);
                    frappe.model.set_value(item.doctype, item.name, 'purchase_invoice_item', matched.name);
                }
            });
            // Set all totals from invoice
            frm.set_value('base_total', pinv.base_total);
            frm.set_value('base_rounded_total', pinv.base_rounded_total);
            frm.set_value('base_grand_total', pinv.base_grand_total);
            frm.set_value('grand_total', pinv.grand_total);
            frm.set_value('rounded_total', pinv.rounded_total);
        }
        // Do NOT call update_total_amount if invoice is present
        update_total_qty(frm)
    });
}

function update_purchase_order_and_purchase_invoice_fields(frm) {
    if (frm.doc.custom_purchase_order_name || frm.doc.custom_purchase_invoice_name) {
        frm.doc.items.forEach(item => {
            if (frm.doc.custom_purchase_order_name) {
                frappe.model.set_value(item.doctype, item.name, 'purchase_order', frm.doc.custom_purchase_order_name);
            }
            if (frm.doc.custom_purchase_invoice_name) {
                frappe.model.set_value(item.doctype, item.name, 'purchase_invoice', frm.doc.custom_purchase_invoice_name);
            }
        });
    }
}

