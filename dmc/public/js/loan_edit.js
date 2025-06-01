frappe.ui.form.on('Loan', {
    applicant: function (frm) {
        if (frm.doc.applicant && frm.doc.applicant_type === "Employee") {
            frappe.db.get_value('Employee', frm.doc.applicant, 'payroll_cost_center')
                .then(r => {
                    if (r.message && r.message.payroll_cost_center) {
                        frm.set_value('cost_center', r.message.payroll_cost_center);
                    }
                });
        }
    }
});
