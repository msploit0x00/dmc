import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from lending.loan_management.doctype.loan_repayment.loan_repayment import LoanRepayment


class CustomLoanRepayment(LoanRepayment):
    """
    Custom Loan Repayment Override
    Purpose: Prevent automatic GL Entry on submit
    """

    def on_submit(self):
        """
        Override on_submit WITHOUT calling super()
        لأننا مش عايزين make_gl_entries() يشتغل
        """
        self.update_loan_status()

    def update_loan_status(self):
        """تحديث حالة القرض بدون عمل GL Entry"""
        if self.against_loan:
            loan = frappe.get_doc("Loan", self.against_loan)
            loan.add_comment(
                "Comment", f"Repayment of {self.amount_paid} via {self.name}")


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

        # الحسابات
        target.paid_to = company.default_cash_account or frappe.db.get_value(
            "Account",
            {"account_type": "Cash", "company": company.name, "is_group": 0},
            "name"
        )
        target.paid_from = loan.loan_account
        target.paid_to_account_currency = company.default_currency
        target.paid_from_account_currency = company.default_currency

        # ✅ رجع الـ References (بس بدون outstanding/allocated)
        target.append("references", {
            "reference_doctype": "Loan Repayment",
            "reference_name": loan_repayment.name,
            "total_amount": loan_repayment.amount_paid,
            "outstanding_amount": 0,  # ✅ صفر عشان الـ validation
            "allocated_amount": 0     # ✅ صفر عشان الـ validation
        })

        # Custom field للربط
        target.loan_repayment = loan_repayment.name

        # Remarks
        target.remarks = f"Payment received for Loan Repayment {loan_repayment.name}"

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
