frappe.ui.form.on('Purchase Receipt', {
    refresh: function (frm) {
        update_total_qty(frm);

        // Add manual trigger button
        frm.add_custom_button("Recalculate Total Qty", () => {
            update_total_qty(frm);
        });

        console.log("✅ Custom Purchase Receipt Client Script loaded");
    },

    items_on_form_rendered: function (frm) {
        update_total_qty(frm);
    }
});

frappe.ui.form.on('Purchase Receipt Item', {
    received_stock_qty: function (frm, cdt, cdn) {
        update_total_qty(frm);
    },
    qty: function (frm, cdt, cdn) {
        update_total_qty(frm);
    },
    items_remove: function (frm) {
        update_total_qty(frm);
    }
});

function update_total_qty(frm) {
    let total = 0;
    (frm.doc.items || []).forEach(item => {
        total += flt(item.received_stock_qty);
    });
    frm.set_value("total_qty", total);
    frm.refresh_field("total_qty");
    console.log("🔢 Updated total_qty:", total);
}
