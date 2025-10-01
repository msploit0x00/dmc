import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from lending.loan_management.doctype.loan_repayment.loan_repayment import LoanRepayment


class CustomLoanRepayment(LoanRepayment):
    """
    Custom Loan Repayment Override
    Purpose: Prevent automatic GL Entry on submit (Payment Entry handles it)
    """

    def on_submit(self):
        """
        ✅ Override WITHOUT calling super() to prevent make_gl_entries()
        """
        # فقط نحدث حالة القرض، بدون GL Entry
        self.update_loan_status()

    def on_cancel(self):
        """
        ✅ Override on_cancel to prevent GL reversal
        """
        # لا نفعل شيء هنا لأن Payment Entry سيتولى الأمر
        pass

    def update_loan_status(self):
        """تحديث حالة القرض بدون عمل GL Entry"""
        if self.against_loan:
            loan = frappe.get_doc("Loan", self.against_loan)
            loan.add_comment(
                "Comment",
                f"Repayment of {self.amount_paid} recorded via {self.name}"
            )

    def make_gl_entries(self, cancel=0, adv_adj=0):
        """
        ✅ Override لمنع أي GL Entries من Loan Repayment
        """
        # لا نفعل شيء - Payment Entry سيتولى GL Entry
        frappe.msgprint(
            _("GL Entry will be created by Payment Entry only"),
            alert=True,
            indicator="blue"
        )
        return


@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
    """إنشاء Payment Entry من Loan Repayment"""

    def set_missing_values(source, target):
        loan_repayment = frappe.get_doc("Loan Repayment", source_name)
        loan = frappe.get_doc("Loan", loan_repayment.against_loan)
        company = frappe.get_doc("Company", loan_repayment.company)

        # إعدادات الـ Payment Entry
        target.payment_type = "Receive"
        target.party_type = "Employee"
        target.party = loan.applicant
        target.paid_amount = loan_repayment.amount_paid
        target.received_amount = loan_repayment.amount_paid
        target.reference_no = loan_repayment.name
        target.reference_date = loan_repayment.posting_date
        target.company = loan_repayment.company
        target.mode_of_payment = "Cash"

        # ✅ الحسابات الصحيحة
        # من: حساب السلفة (Loan Account)
        target.paid_from = loan.loan_account

        # إلى: حساب الخزينة (Cash Account)
        target.paid_to = company.default_cash_account or frappe.db.get_value(
            "Account",
            {"account_type": "Cash", "company": company.name, "is_group": 0},
            "name"
        )

        target.paid_to_account_currency = company.default_currency
        target.paid_from_account_currency = company.default_currency

        # ✅ References للربط فقط (بدون outstanding)
        target.append("references", {
            "reference_doctype": "Loan Repayment",
            "reference_name": loan_repayment.name,
            "total_amount": loan_repayment.amount_paid,
            "outstanding_amount": 0,
            "allocated_amount": 0
        })

        # ✅ Custom field للربط
        target.loan_repayment = loan_repayment.name

        # Remarks
        target.remarks = f"Payment received for Loan Repayment {loan_repayment.name} against Loan {loan.name}"

    doc = get_mapped_doc(
        "Loan Repayment",
        source_name,
        {
            "Loan Repayment": {
                "doctype": "Payment Entry",
                "field_map": {
                    "posting_date": "posting_date",
                    "company": "company"
                }
            }
        },
        target_doc,
        set_missing_values
    )

    return doc
