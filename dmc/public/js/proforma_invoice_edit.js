frappe.ui.form.on('Proforma Invoice Item', {
    item_code: function (frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        if (!row.item_code) return;

        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Batch",
                filters: { item: row.item_code },
                fields: ["batch_id", "custom_gtin"],
                limit_page_length: 1,
                order_by: "creation desc"
            },
            callback: function (r) {
                if (r.message && r.message.length) {
                    let batch = r.message[0];
                    frappe.model.set_value(cdt, cdn, "batch_no", batch.batch_id);     // set batch_id here
                    frappe.model.set_value(cdt, cdn, "custom_gtin", batch.custom_gtin); // set custom_gtin
                    frm.refresh_field("items");
                } else {
                    frappe.model.set_value(cdt, cdn, "batch_no", "");
                    frappe.model.set_value(cdt, cdn, "custom_gtin", "");
                    frm.refresh_field("items");
                }
            }
        });
    }
});
