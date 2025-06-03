frappe.ui.form.on("Bank Guarantee", {
    bg_type: function (frm) {
        frm.set_value("reference_doctype", "Payment Entry");
        console.log("Bank Guarantee Type changed to: " + frm.doc.bg_type);
    }
});
