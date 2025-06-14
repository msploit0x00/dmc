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
        // Update purchase order and purchase invoice fields for all items


        // Keep the existing functionality
        setTimeout(function () {
            fetch_invoice_data_for_items(frm);
            update_purchase_order_and_purchase_invoice_fields(frm);
            // --- Fix: recalculate received_stock_qty for all items after barcode scan ---
            (frm.doc.items || []).forEach(item => {
                if (item.qty && item.conversion_factor) {
                    frappe.model.set_value(item.doctype, item.name, 'received_stock_qty', flt(item.qty) * flt(item.conversion_factor));
                }
            });
        }, 500); // 500ms delay
    },

    // You might also want to catch any manual row addition
    items_add: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (frm.doc.custom_purchase_order_name) {
            frappe.model.set_value(cdt, cdn, 'purchase_order', frm.doc.custom_purchase_order_name);
        }
    },

    refresh: function (frm) {
        // Add custom button if needed
        // frm.add_custom_button(__('Fetch Base Amount'), function () {
        //     fetchBaseAmount(frm);
        // });
    }

    // before_save: function (frm) {
    //     update_total_qty(frm);

    //     // Add manual trigger button
    //     // frm.add_custom_button("Recalculate Total Qty", () => {
    //     //     update_total_qty(frm);
    //     // });

    //     console.log("✅ Before Save Custom Purchase Receipt Client Script loaded");
    // },
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
        // Only update received_stock_qty, then fetch invoice data
        let row = locals[cdt][cdn];
        if (row.qty && row.conversion_factor) {
            frappe.model.set_value(cdt, cdn, 'received_stock_qty', flt(row.qty) * flt(row.conversion_factor));
        }
        setTimeout(function () {
            fetch_invoice_data_for_items(frm);
        }, 500);
    },

    qty: function (frm, cdt, cdn) {
        // Only update received_stock_qty, then fetch invoice data
        let row = locals[cdt][cdn];
        if (row.qty && row.conversion_factor) {
            frappe.model.set_value(cdt, cdn, 'received_stock_qty', flt(row.qty) * flt(row.conversion_factor));
        }
        update_total_qty(frm);
        frappe.model.set_value(cdt, cdn, 'batch_no', null);
        setTimeout(function () {
            fetch_invoice_data_for_items(frm);
        }, 500);
    },

    base_rate: function (frm, cdt, cdn) {
        // No local calculation for base_amount here
    },

    item_code: function (frm, cdt, cdn) {
        fetch_invoice_data_for_items(frm);
    }
});

function update_total_qty(frm) {
    // Only update if not submitted
    if (frm.doc.docstatus === 1) return;
    let total = 0;
    (frm.doc.items || []).forEach(item => {
        total += flt(item.received_stock_qty);
    });
    frm.set_value("total_qty", total);
    frm.refresh_field("total_qty");
}


function update_total_amount(frm) {
    // Only update if not submitted
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
                    frappe.model.set_value(item.doctype, item.name, 'base_amount', matched.base_amount);
                    frappe.model.set_value(item.doctype, item.name, 'stock_uom_rate', matched.stock_uom_rate);
                    frappe.model.set_value(item.doctype, item.name, 'net_rate', matched.net_rate);
                    frappe.model.set_value(item.doctype, item.name, 'net_amount', matched.net_amount);
                    frappe.model.set_value(item.doctype, item.name, 'base_net_rate', matched.base_net_rate);
                    frappe.model.set_value(item.doctype, item.name, 'base_net_amount', matched.base_net_amount);
                }
            });
            frm.set_value('rounded_total', pinv.rounded_total);
            frm.set_value('grand_total', pinv.grand_total);
        }
        update_total_amount(frm)
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

