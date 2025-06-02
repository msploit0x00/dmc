frappe.ui.form.on("Bank Guarantee", {
    bg_type: function (frm) {
        frm.set_value("reference_doctype", "Payment Entry");
    }
});
