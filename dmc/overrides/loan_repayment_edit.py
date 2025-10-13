# import frappe
# from frappe import _
# from frappe.model.mapper import get_mapped_doc
# from lending.loan_management.doctype.loan_repayment.loan_repayment import LoanRepayment


# class CustomLoanRepayment(LoanRepayment):
#     """
#     Custom Loan Repayment Override
#     Purpose: Prevent automatic GL Entry on submit (Payment Entry handles it)
#     """

#     def on_submit(self):
#         """
#         ✅ Override WITHOUT calling super() to prevent make_gl_entries()
#         """
#         # فقط نحدث حالة القرض، بدون GL Entry
#         self.update_loan_status()

#     def on_cancel(self):
#         """
#         ✅ Override on_cancel to prevent GL reversal
#         """
#         # لا نفعل شيء هنا لأن Payment Entry سيتولى الأمر
#         pass

#     def update_loan_status(self):
#         """تحديث حالة القرض بدون عمل GL Entry"""
#         if self.against_loan:
#             loan = frappe.get_doc("Loan", self.against_loan)
#             loan.add_comment(
#                 "Comment",
#                 f"Repayment of {self.amount_paid} recorded via {self.name}"
#             )

#     def make_gl_entries(self, cancel=0, adv_adj=0):
#         """
#         ✅ Override لمنع أي GL Entries من Loan Repayment
#         """
#         # لا نفعل شيء - Payment Entry سيتولى GL Entry
#         frappe.msgprint(
#             _("GL Entry will be created by Payment Entry only"),
#             alert=True,
#             indicator="blue"
#         )
#         return


# @frappe.whitelist()
# def make_payment_entry(source_name, target_doc=None):
#     """إنشاء Payment Entry من Loan Repayment"""

#     def set_missing_values(source, target):
#         loan_repayment = frappe.get_doc("Loan Repayment", source_name)
#         loan = frappe.get_doc("Loan", loan_repayment.against_loan)
#         company = frappe.get_doc("Company", loan_repayment.company)

#         # إعدادات الـ Payment Entry
#         target.payment_type = "Receive"
#         target.party_type = "Employee"
#         target.party = loan.applicant
#         target.paid_amount = loan_repayment.amount_paid
#         target.received_amount = loan_repayment.amount_paid
#         target.reference_no = loan_repayment.name
#         target.reference_date = loan_repayment.posting_date
#         target.company = loan_repayment.company
#         target.mode_of_payment = "Cash"

#         # ✅ الحسابات الصحيحة
#         # من: حساب السلفة (Loan Account)
#         target.paid_from = loan.loan_account

#         # إلى: حساب الخزينة (Cash Account)
#         target.paid_to = company.default_cash_account or frappe.db.get_value(
#             "Account",
#             {"account_type": "Cash", "company": company.name, "is_group": 0},
#             "name"
#         )

#         target.paid_to_account_currency = company.default_currency
#         target.paid_from_account_currency = company.default_currency

#         # ✅ References للربط فقط (بدون outstanding)
#         target.append("references", {
#             "reference_doctype": "Loan Repayment",
#             "reference_name": loan_repayment.name,
#             "total_amount": loan_repayment.amount_paid,
#             "outstanding_amount": 0,
#             "allocated_amount": 0
#         })

#         # ✅ Custom field للربط
#         target.loan_repayment = loan_repayment.name

#         # Remarks
#         target.remarks = f"Payment received for Loan Repayment {loan_repayment.name} against Loan {loan.name}"

#     doc = get_mapped_doc(
#         "Loan Repayment",
#         source_name,
#         {
#             "Loan Repayment": {
#                 "doctype": "Payment Entry",
#                 "field_map": {
#                     "posting_date": "posting_date",
#                     "company": "company"
#                 }
#             }
#         },
#         target_doc,
#         set_missing_values
#     )

#     return doc

#############################################################
import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from lending.loan_management.doctype.loan_repayment.loan_repayment import LoanRepayment


class CustomLoanRepayment(LoanRepayment):
    """
    Custom Loan Repayment Override
    Purpose: 
    - From Salary Slip: Create GL Entry automatically
    - Manual (after resignation): NO GL Entry (Payment Entry handles it)
    """

    def on_submit(self):
        """
        ✅ Create GL Entry ONLY if from Salary Slip
        ✅ Skip GL Entry if manual payment (after resignation)
        """
        if self.is_manual_payment():
            # Manual payment after resignation - NO GL Entry
            # Only update loan status
            self.update_paid_amount_in_loan()
            self.set_status_in_loan()

            frappe.msgprint(
                _("Loan Repayment submitted without GL Entry. Create Payment Entry to complete the transaction."),
                alert=True,
                indicator="blue"
            )
        else:
            # From Salary Slip - create GL Entry (Core behavior)
            super(CustomLoanRepayment, self).on_submit()
            frappe.msgprint(
                _("Loan Repayment submitted. GL Entry created from Salary Slip."),
                alert=True,
                indicator="green"
            )

    def on_cancel(self):
        """
        ✅ Cancel GL Entry ONLY if it exists (from Salary Slip)
        """
        # Check if GL Entry exists
        has_gl_entry = frappe.db.exists("GL Entry", {
            "voucher_type": "Loan Repayment",
            "voucher_no": self.name,
            "is_cancelled": 0
        })

        if has_gl_entry:
            # From Salary Slip - cancel GL Entry
            super(CustomLoanRepayment, self).on_cancel()
        else:
            # Manual - just update loan status
            self.update_paid_amount_in_loan()
            self.set_status_in_loan()

        # Unlink Payment Entry if exists
        if self.payment_entry:
            frappe.db.set_value("Loan Repayment", self.name,
                                "payment_entry", None)

    def make_gl_entries(self, cancel=0, adv_adj=0):
        """
        ✅ CRITICAL: Override to prevent GL Entry for manual payments
        """
        if self.is_manual_payment():
            # Manual payment - Skip GL Entry completely
            frappe.logger().info(
                f"Skipping GL Entry for manual Loan Repayment {self.name}. "
                f"GL Entry will be created via Payment Entry."
            )
            return None

        # From Salary Slip - create GL Entry (Core behavior)
        return super(CustomLoanRepayment, self).make_gl_entries(cancel=cancel, adv_adj=adv_adj)

    def validate(self):
        """Add validation"""
        super(CustomLoanRepayment, self).validate()

        # Warn if Payment Entry already exists
        if self.payment_entry and self.docstatus == 0:
            pe_status = frappe.db.get_value(
                "Payment Entry", self.payment_entry, "docstatus")
            if pe_status == 1:
                frappe.msgprint(
                    _("This Loan Repayment is linked to submitted Payment Entry {0}").format(
                        frappe.bold(self.payment_entry)
                    ),
                    alert=True,
                    indicator="orange"
                )

    def is_manual_payment(self):
        """
        ✅ Check if this is a manual payment (after resignation)

        Returns: True if manual payment, False if from Salary Slip

        Logic:
        1. Check custom field 'is_manual_payment' (user explicitly marks it)
        2. If not set, check if payroll_payable_account exists (from Salary Slip)
        """
        # Method 1: Check custom field (explicitly marked as manual)
        if hasattr(self, 'is_manual_payment') and self.is_manual_payment:
            return True

        # Method 2: If payroll_payable_account exists = from Salary Slip
        if self.payroll_payable_account:
            return False

        # Method 3: Check if linked to Salary Slip
        salary_slip_loan = frappe.db.exists("Salary Slip Loan", {
            "loan_repayment_entry": self.name
        })
        if salary_slip_loan:
            return False

        # Default: If no payroll account and not from salary slip = assume manual
        # This handles the case where user forgets to check the box
        return True

    def update_paid_amount_in_loan(self):
        """Update the paid amount in the loan document"""
        if self.against_loan:
            loan = frappe.get_doc("Loan", self.against_loan)

            # Calculate total paid amount
            total_paid = frappe.db.sql("""
                SELECT IFNULL(SUM(amount_paid), 0)
                FROM `tabLoan Repayment`
                WHERE against_loan = %s
                AND docstatus = 1
            """, self.against_loan)[0][0]

            # Update loan
            loan.db_set("total_amount_paid", total_paid)

    def set_status_in_loan(self):
        """Update loan status based on payment"""
        if self.against_loan:
            from lending.loan_management.doctype.loan.loan import Loan
            loan = frappe.get_doc("Loan", self.against_loan)
            loan.set_status()
            loan.db_set("status", loan.status)


@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
    """
    Create Payment Entry from Loan Repayment
    ✅ This creates the GL Entry for manual payments
    """

    def set_missing_values(source, target):
        loan_repayment = frappe.get_doc("Loan Repayment", source_name)

        # ✅ Validate: Loan Repayment must be submitted
        if loan_repayment.docstatus != 1:
            frappe.throw(
                _("Loan Repayment must be submitted before creating Payment Entry"))

        # ✅ Check if Payment Entry already exists
        if loan_repayment.payment_entry:
            frappe.throw(
                _("Payment Entry {0} already exists for this Loan Repayment").format(
                    frappe.bold(loan_repayment.payment_entry)
                )
            )

        # ✅ Don't allow Payment Entry for Salary Slip repayments
        if loan_repayment.payroll_payable_account and not getattr(loan_repayment, 'is_manual_payment', False):
            frappe.throw(
                _("Cannot create Payment Entry for Loan Repayment from Salary Slip. "
                  "GL Entry is already created via Salary Slip accounting.")
            )

        loan = frappe.get_doc("Loan", loan_repayment.against_loan)
        company = frappe.get_doc("Company", loan_repayment.company)

        # Payment Entry Configuration
        target.payment_type = "Receive"
        target.party_type = "Employee"
        target.party = loan.applicant
        target.paid_amount = loan_repayment.amount_paid
        target.received_amount = loan_repayment.amount_paid
        target.reference_no = loan_repayment.name
        target.reference_date = loan_repayment.posting_date
        target.company = loan_repayment.company
        target.mode_of_payment = "Cash"

        # ✅ Account Configuration
        # This creates THE GL Entry:
        # Debit: Cash Account (money received)
        # Credit: Loan Account (reduce loan liability)
        target.paid_from = loan.loan_account

        # Get Cash Account
        target.paid_to = company.default_cash_account or frappe.db.get_value(
            "Account",
            {"account_type": "Cash", "company": company.name, "is_group": 0},
            "name"
        )

        if not target.paid_to:
            frappe.throw(
                _("Please set Default Cash Account in Company {0}").format(
                    company.name)
            )

        target.paid_to_account_currency = company.default_currency
        target.paid_from_account_currency = company.default_currency

        # ✅ References for linking
        target.append("references", {
            "reference_doctype": "Loan Repayment",
            "reference_name": loan_repayment.name,
            "total_amount": loan_repayment.amount_paid,
            "outstanding_amount": 0,
            "allocated_amount": 0
        })

        # ✅ Custom field for tracking
        if hasattr(target, 'loan_repayment'):
            target.loan_repayment = loan_repayment.name

        # Remarks
        target.remarks = (
            f"Manual payment received for Loan Repayment {loan_repayment.name} "
            f"against Loan {loan.name} for Employee {loan.applicant} (After Resignation)"
        )

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


@frappe.whitelist()
def get_remaining_loan_amount(loan_id):
    """Get remaining loan amount for early settlement"""
    loan = frappe.get_doc("Loan", loan_id)

    total_payable = loan.total_payment

    total_paid = frappe.db.sql("""
        SELECT IFNULL(SUM(amount_paid), 0)
        FROM `tabLoan Repayment`
        WHERE against_loan = %s
        AND docstatus = 1
    """, loan_id)[0][0]

    remaining = total_payable - total_paid

    return {
        "total_payable": total_payable,
        "total_paid": total_paid,
        "remaining": remaining
    }


@frappe.whitelist()
def get_loan_repayment_details(loan_repayment):
    """Get details of Loan Repayment for Payment Entry"""
    doc = frappe.get_doc("Loan Repayment", loan_repayment)
    loan = frappe.get_doc("Loan", doc.against_loan)

    return {
        "employee": loan.applicant,
        "employee_name": frappe.db.get_value("Employee", loan.applicant, "employee_name"),
        "loan": doc.against_loan,
        "amount": doc.amount_paid,
        "loan_account": loan.loan_account,
        "posting_date": doc.posting_date,
        "from_salary_slip": bool(doc.payroll_payable_account),
        "is_manual": bool(getattr(doc, 'is_manual_payment', False))
    }
