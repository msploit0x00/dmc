frappe.ui.form.on('Purchase Receipt', {
    // validate(frm) {
    //     fetchBaseAmountFromInvoice(frm);
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
        update_total_amount(frm)

        // Add manual trigger button
        // frm.add_custom_button("Recalculate Total Qty", () => {
        //     update_total_qty(frm);
        // });

        console.log("✅ Custom Purchase Receipt Client Script loaded");
    },

    items_on_form_rendered: function (frm) {
        update_total_qty(frm);
        update_total_amount(frm)
    },

    scan_barcode: function (frm) {
        // Wait for the item row to be added
        setTimeout(() => {
            let last_item = frm.doc.items && frm.doc.items[frm.doc.items.length - 1];
            if (last_item && frm.doc.custom_purchase_order_name) {
                frappe.model.set_value(last_item.doctype, last_item.name, 'purchase_order', frm.doc.custom_purchase_order_name);
            }

        }, 300);
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
        frm.add_custom_button(__('Fetch Base Amount'), function () {
            fetchBaseAmount(frm);
        });
    }

    // before_save: function (frm) {
    //     update_total_qty(frm);

    //     // Add manual trigger button
    //     // frm.add_custom_button("Recalculate Total Qty", () => {
    //     //     update_total_qty(frm);
    //     // });

    //     console.log("✅ Before Save Custom Purchase Receipt Client Script loaded");
    // },

    // after_save: function (frm, cdt, cdn) {
    //     fetchingValueOfStockRateUom(frm, cdt, cdn)



    // },
});

frappe.ui.form.on('Purchase Receipt Item', {

    received_stock_qty: function (frm, cdt, cdn) {
        update_total_qty(frm);

    },
    qty: function (frm, cdt, cdn) {
        update_total_qty(frm);
    },
    items_add: function (frm) {
        fetchBaseAmount(frm, cdt, cdn);

    },
    items_remove: function (frm) {
        update_total_qty(frm);
        update_total_amount(frm)
    },

    uom: function (frm, cdt, cdn) {
        fetchingValueOfStockRateUom(frm, cdt, cdn)
        // fetchBaseAmountFromInvoice(frm, cdt, cdn);
        fetchBaseAmount(frm, cdt, cdn);


    },
    qty: function (frm, cdt, cdn) {
        fetchingValueOfStockRateUom(frm, cdt, cdn)
        fetchBaseAmount(frm, cdt, cdn);


    },

    purchase_invoice: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.purchase_invoice) {
            fetchBaseAmount(frm, cdt, cdn);
        }
    },



});

function update_total_qty(frm) {
    let total = 0;
    (frm.doc.items || []).forEach(item => {
        total += flt(item.received_stock_qty);
    });
    frm.set_value("total_qty", total);
    frm.refresh_field("total_qty");

}


function update_total_amount(frm) {
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

// function fetchBaseAmountFromInvoice(frm, cdt, cdn) {
//     if (!frm.doc.items || frm.doc.items.length === 0) {
//         frappe.msgprint(__("No items found in the table."));
//         return;
//     }

//     setTimeout(() => {
//         frm.doc.items.forEach(item => {
//             if (item.purchase_invoice) {
//                 frappe.db.get_doc("Purchase Invoice", item.purchase_invoice).then(purchase_invoice => {
//                     console.log("📄 Fetched Purchase Invoice:", purchase_invoice);
//                     if (purchase_invoice && purchase_invoice.items) {
//                         let matched_item = purchase_invoice.items.find(pi_item => pi_item.item_code === item.item_code);

//                         if (matched_item) {
//                             frappe.model.set_value(item.doctype, item.name, "base_amount", matched_item.base_amount);
//                         }
//                     }
//                 });
//             }
//         });
//     }, 1000);
// }

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

