frappe.ui.form.on('Quotation', {
    validate(frm) {
        if (frm.doc.grand_total) {
            frappe.call({
                method: "dmc.api.money_to_arabic_words",  // full Python path
                args: {
                    amount: frm.doc.rounded_total
                },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value("custom_amount_in_words_arabic", r.message);
                    }
                }
            });
        }
    }
});
