frappe.ui.form.on('Loan Repayment', {
    refresh: function (frm) {
        // لو submitted ومفيش Payment Entry
        if (frm.doc.docstatus === 1 && !frm.doc.payment_entry) {
            // ✅ اعمل الزرار في الـ Menu مباشرة (مش Create group)
            frm.add_custom_button(__('Create Payment Entry'), function () {
                frappe.call({
                    method: 'dmc.overrides.loan_repayment_edit.make_payment_entry',
                    args: {
                        'source_name': frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __('Creating Payment Entry...'),
                    callback: function (r) {
                        if (r.message) {
                            var doc = frappe.model.sync(r.message);
                            frappe.set_route('Form', doc[0].doctype, doc[0].name);
                        }
                    }
                });
            }).addClass('btn-primary');  // ✅ شيل __('Create') من هنا
        }

        // لو في Payment Entry، اعرض link
        if (frm.doc.payment_entry) {
            frm.add_custom_button(__('View Payment Entry'), function () {
                frappe.set_route('Form', 'Payment Entry', frm.doc.payment_entry);
            });
        }
    }
});