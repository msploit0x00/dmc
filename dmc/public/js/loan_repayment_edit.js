frappe.ui.form.on('Loan Repayment', {
    refresh: function (frm) {
        // ✅ زرار إنشاء Payment Entry
        if (frm.doc.docstatus === 1 && !frm.doc.payment_entry) {
            frm.add_custom_button(__('إنشاء Payment Entry'), function () {
                frappe.call({
                    method: 'dmc.overrides.loan_repayment_edit.make_payment_entry',
                    args: {
                        'source_name': frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __('جاري إنشاء Payment Entry...'),
                    callback: function (r) {
                        if (r.message) {
                            var doc = frappe.model.sync(r.message);
                            frappe.set_route('Form', doc[0].doctype, doc[0].name);
                        }
                    }
                });
            }).addClass('btn-primary');
        }

        // ✅ زرار عرض Payment Entry
        if (frm.doc.payment_entry) {
            frm.add_custom_button(__('عرض Payment Entry'), function () {
                frappe.set_route('Form', 'Payment Entry', frm.doc.payment_entry);
            });
        }

        // ✅ زرار حساب باقي المبلغ (للتسوية المبكرة)
        if (frm.doc.docstatus === 0 && frm.doc.against_loan && !frm.doc.payroll_payable_account) {
            frm.add_custom_button(__('حساب باقي المبلغ الكلي'), function () {
                calculate_remaining_amount(frm);
            }, __('أدوات'));
        }
    },

    against_loan: function (frm) {
        // ✅ لو اختار قرض، اعرض معلومات القرض
        if (frm.doc.against_loan) {
            show_loan_info(frm);
        }
    },

    // ✅ لو غير تاريخ الاستحقاق وكان قبل اليوم، احسب القسط الشهري فقط
    due_date: function (frm) {
        if (frm.doc.against_loan && !frm.doc.payroll_payable_account) {
            auto_calculate_amount(frm);
        }
    }
});

// ✅ دالة حساب باقي المبلغ الكلي
function calculate_remaining_amount(frm) {
    if (!frm.doc.against_loan) {
        frappe.msgprint(__('اختر القرض أولاً'));
        return;
    }

    frappe.call({
        method: 'dmc.overrides.loan_repayment_edit.get_remaining_loan_amount',
        args: {
            'loan_id': frm.doc.against_loan
        },
        freeze: true,
        callback: function (r) {
            if (r.message) {
                const data = r.message;

                frm.set_value('amount_paid', data.remaining);

                frappe.msgprint({
                    title: __('معلومات القرض'),
                    message: `
                        <div style="line-height: 1.8;">
                            <strong>إجمالي المبلغ المطلوب:</strong> ${format_currency(data.total_payable)}<br>
                            <strong>المدفوع:</strong> ${format_currency(data.total_paid)}<br>
                            <strong style="color: #4CAF50; font-size: 16px;">الباقي:</strong> 
                            <strong style="color: #4CAF50; font-size: 16px;">${format_currency(data.remaining)}</strong>
                        </div>
                    `,
                    indicator: 'blue'
                });
            }
        }
    });
}

// ✅ دالة عرض معلومات القرض
function show_loan_info(frm) {
    frappe.call({
        method: 'dmc.overrides.loan_repayment_edit.get_remaining_loan_amount',
        args: {
            'loan_id': frm.doc.against_loan
        },
        callback: function (r) {
            if (r.message) {
                const data = r.message;
                frm.dashboard.add_comment(
                    `الباقي من القرض: <strong>${format_currency(data.remaining)}</strong>`,
                    'blue',
                    true
                );
            }
        }
    });
}

// ✅ دالة الحساب التلقائي (قسط شهري أو كامل المبلغ)
function auto_calculate_amount(frm) {
    const today = frappe.datetime.get_today();
    const due_date = frm.doc.due_date;

    // لو تاريخ الاستحقاق في المستقبل = تسوية مبكرة
    if (due_date && frappe.datetime.str_to_obj(due_date) > frappe.datetime.str_to_obj(today)) {
        frappe.confirm(
            __('تاريخ الاستحقاق في المستقبل. هل تريد حساب باقي المبلغ الكلي للتسوية المبكرة؟'),
            function () {
                calculate_remaining_amount(frm);
            }
        );
    }
}

// ✅ دالة تنسيق العملة
function format_currency(value) {
    return frappe.format(value, { fieldtype: 'Currency' });
}