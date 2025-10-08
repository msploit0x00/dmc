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

# import frappe
# from frappe import _
# from frappe.model.mapper import get_mapped_doc
# from lending.loan_management.doctype.loan_repayment.loan_repayment import LoanRepayment


# class CustomLoanRepayment(LoanRepayment):
#     """
#     Custom Loan Repayment Override
#     Purpose:
#     - From Salary Slip: Create GL Entry (core behavior)
#     - Manual creation: NO GL Entry (Payment Entry will handle it)
#     """

#     def on_submit(self):
#         """
#         ✅ Create GL Entry ONLY if from Salary Slip
#         ✅ Skip GL Entry if manual (Payment Entry will handle it)
#         """
#         if self.is_from_salary_slip():
#             # From Salary Slip - call parent to create GL Entry
#             super(CustomLoanRepayment, self).on_submit()
#             frappe.msgprint(
#                 _("Loan Repayment submitted. GL Entry created from Salary Slip."),
#                 alert=True,
#                 indicator="green"
#             )
#         else:
#             # Manual creation - skip parent, only update loan without GL Entry
#             # We manually call only the necessary methods without GL Entry
#             self.update_paid_amount_in_loan()
#             self.set_status_in_loan()

#             frappe.msgprint(
#                 _("Loan Repayment submitted. Create Payment Entry to record the actual payment."),
#                 alert=True,
#                 indicator="blue"
#             )

#     def on_cancel(self):
#         """
#         ✅ Cancel GL Entry ONLY if it exists (from Salary Slip)
#         """
#         # Check if GL Entry exists
#         has_gl_entry = frappe.db.exists("GL Entry", {
#             "voucher_type": "Loan Repayment",
#             "voucher_no": self.name,
#             "is_cancelled": 0
#         })

#         if has_gl_entry:
#             # From Salary Slip - cancel GL Entry
#             super(CustomLoanRepayment, self).on_cancel()
#         else:
#             # Manual - just update loan status without GL cancellation
#             self.update_paid_amount_in_loan()
#             self.set_status_in_loan()

#         # Unlink Payment Entry if exists
#         if self.payment_entry:
#             frappe.db.set_value("Loan Repayment", self.name,
#                                 "payment_entry", None)

#     def update_paid_amount_in_loan(self):
#         """Update the paid amount in the loan document"""
#         if self.against_loan:
#             loan = frappe.get_doc("Loan", self.against_loan)

#             # Calculate total paid amount
#             total_paid = frappe.db.sql("""
#                 SELECT IFNULL(SUM(amount_paid), 0)
#                 FROM `tabLoan Repayment`
#                 WHERE against_loan = %s
#                 AND docstatus = 1
#             """, self.against_loan)[0][0]

#             # Update loan
#             loan.db_set("total_amount_paid", total_paid)

#     def set_status_in_loan(self):
#         """Update loan status based on payment"""
#         if self.against_loan:
#             from lending.loan_management.doctype.loan.loan import Loan
#             loan = frappe.get_doc("Loan", self.against_loan)
#             loan.set_status()
#             loan.db_set("status", loan.status)

#     def make_gl_entries(self, cancel=0, adv_adj=0):
#         """
#         ✅ Override to prevent GL Entry for manual Loan Repayments
#         Only create GL Entry if from Salary Slip
#         """
#         if self.is_from_salary_slip():
#             # From Salary Slip - create GL Entry
#             return super(CustomLoanRepayment, self).make_gl_entries(cancel=cancel, adv_adj=adv_adj)
#         else:
#             # Manual - skip GL Entry completely
#             return None

#     def validate(self):
#         """Add validation"""
#         super(CustomLoanRepayment, self).validate()

#         # Warn if Payment Entry already exists
#         if self.payment_entry and self.docstatus == 0:
#             pe_status = frappe.db.get_value(
#                 "Payment Entry", self.payment_entry, "docstatus")
#             if pe_status == 1:
#                 frappe.msgprint(
#                     _("This Loan Repayment is linked to submitted Payment Entry {0}").format(
#                         frappe.bold(self.payment_entry)
#                     ),
#                     alert=True,
#                     indicator="orange"
#                 )

#     def is_from_salary_slip(self):
#         """
#         Check if this Loan Repayment was created from Salary Slip
#         Returns: True if from Salary Slip, False if manual
#         """
#         # Method 1: Check if payroll_payable_account is set
#         if self.payroll_payable_account:
#             return True

#         # Method 2: Check if referenced in Salary Slip Loan child table
#         salary_slip_loan = frappe.db.exists("Salary Slip Loan", {
#             "loan_repayment_entry": self.name
#         })
#         if salary_slip_loan:
#             return True

#         return False


# @frappe.whitelist()
# def make_payment_entry(source_name, target_doc=None):
#     """
#     Create Payment Entry from Loan Repayment
#     ✅ This creates the ONLY GL Entry for manual Loan Repayments
#     """

#     def set_missing_values(source, target):
#         loan_repayment = frappe.get_doc("Loan Repayment", source_name)

#         # ✅ Validate: Loan Repayment must be submitted
#         if loan_repayment.docstatus != 1:
#             frappe.throw(
#                 _("Loan Repayment must be submitted before creating Payment Entry"))

#         # ✅ Don't allow Payment Entry for Salary Slip Loan Repayments
#         if loan_repayment.payroll_payable_account:
#             frappe.throw(
#                 _("Cannot create Payment Entry for Loan Repayment from Salary Slip. "
#                   "GL Entry is already created via payroll accounting.")
#             )

#         # ✅ Check if Payment Entry already exists
#         if loan_repayment.payment_entry:
#             frappe.throw(
#                 _("Payment Entry {0} already exists for this Loan Repayment").format(
#                     frappe.bold(loan_repayment.payment_entry)
#                 )
#             )

#         loan = frappe.get_doc("Loan", loan_repayment.against_loan)
#         company = frappe.get_doc("Company", loan_repayment.company)

#         # Payment Entry Configuration
#         target.payment_type = "Receive"
#         target.party_type = "Employee"
#         target.party = loan.applicant
#         target.paid_amount = loan_repayment.amount_paid
#         target.received_amount = loan_repayment.amount_paid
#         target.reference_no = loan_repayment.name
#         target.reference_date = loan_repayment.posting_date
#         target.company = loan_repayment.company
#         target.mode_of_payment = "Cash"

#         # ✅ Account Configuration
#         # This creates THE ONLY GL Entry:
#         # Debit: Cash Account (money received)
#         # Credit: Loan Account (reduce loan liability)

#         target.paid_from = loan.loan_account

#         # Get Cash Account
#         target.paid_to = company.default_cash_account or frappe.db.get_value(
#             "Account",
#             {"account_type": "Cash", "company": company.name, "is_group": 0},
#             "name"
#         )

#         if not target.paid_to:
#             frappe.throw(
#                 _("Please set Default Cash Account in Company {0}").format(company.name))

#         target.paid_to_account_currency = company.default_currency
#         target.paid_from_account_currency = company.default_currency

#         # ✅ References for linking
#         target.append("references", {
#             "reference_doctype": "Loan Repayment",
#             "reference_name": loan_repayment.name,
#             "total_amount": loan_repayment.amount_paid,
#             "outstanding_amount": 0,
#             "allocated_amount": 0
#         })

#         # ✅ Custom field for tracking
#         if hasattr(target, 'loan_repayment'):
#             target.loan_repayment = loan_repayment.name

#         # Remarks
#         target.remarks = (
#             f"Cash payment received for Loan Repayment {loan_repayment.name} "
#             f"against Loan {loan.name} for Employee {loan.applicant}"
#         )

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


# @frappe.whitelist()
# def get_loan_repayment_details(loan_repayment):
#     """
#     Get details of Loan Repayment for Payment Entry
#     """
#     doc = frappe.get_doc("Loan Repayment", loan_repayment)
#     loan = frappe.get_doc("Loan", doc.against_loan)

#     return {
#         "employee": loan.applicant,
#         "employee_name": frappe.db.get_value("Employee", loan.applicant, "employee_name"),
#         "loan": doc.against_loan,
#         "amount": doc.amount_paid,
#         "loan_account": loan.loan_account,
#         "posting_date": doc.posting_date,
#         "from_salary_slip": bool(doc.payroll_payable_account)
#     }


import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from lending.loan_management.doctype.loan_repayment.loan_repayment import LoanRepayment


class CustomLoanRepayment(LoanRepayment):
    """
    Custom Loan Repayment Override
    Purpose: 
    - From Salary Slip (شهري): Create GL Entry automatically
    - Manual (استقالة/تسوية): NO GL Entry until Payment Entry
    - يدعم دفع باقي الأقساط دفعة واحدة
    """

    def validate(self):
        """Add validation"""
        super(CustomLoanRepayment, self).validate()

        # ✅ لو Manual وتاريخ الاستحقاق مستقبلي، اجلب باقي الأقساط
        if not self.is_from_salary_slip() and self.is_early_settlement():
            self.calculate_remaining_amount()

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

    def calculate_remaining_amount(self):
        """
        ✅ حساب باقي المبلغ الكلي للقرض (للتسوية المبكرة)
        """
        if not self.against_loan:
            return

        loan = frappe.get_doc("Loan", self.against_loan)

        # إجمالي المبلغ المطلوب (أصل + فوائد)
        total_payable = loan.total_payment

        # المبلغ المدفوع فعلياً
        total_paid = frappe.db.sql("""
            SELECT IFNULL(SUM(amount_paid), 0)
            FROM `tabLoan Repayment`
            WHERE against_loan = %s
            AND docstatus = 1
            AND name != %s
        """, (self.against_loan, self.name or ""))[0][0]

        # الباقي
        remaining = total_payable - total_paid

        if remaining > 0:
            self.amount_paid = remaining
            frappe.msgprint(
                _("تم حساب باقي المبلغ الكلي: {0}").format(
                    frappe.bold(frappe.format_value(
                        remaining, {"fieldtype": "Currency"}))
                ),
                alert=True,
                indicator="blue"
            )

    def is_early_settlement(self):
        """
        ✅ تحقق: هل ده تسوية مبكرة (دفع قبل موعد الاستحقاق)؟
        """
        if not self.against_loan or not self.due_date:
            return False

        from frappe.utils import getdate, nowdate

        # لو تاريخ الاستحقاق في المستقبل = تسوية مبكرة
        return getdate(self.due_date) > getdate(nowdate())

    def on_submit(self):
        """
        ✅ Create GL Entry ONLY if from Salary Slip
        ✅ Manual: Update loan only, wait for Payment Entry
        """
        if self.is_from_salary_slip():
            # From Salary Slip - call parent to create GL Entry
            super(CustomLoanRepayment, self).on_submit()
            frappe.msgprint(
                _("تم رفع قيد من كشف المرتب"),
                alert=True,
                indicator="green"
            )
        else:
            # Manual - skip GL Entry, only update loan
            self.update_paid_amount_in_loan()
            self.set_status_in_loan()

            frappe.msgprint(
                _("تم حفظ السداد. اعمل Payment Entry لرفع القيد المحاسبي"),
                alert=True,
                indicator="blue"
            )

    def on_cancel(self):
        """
        ✅ Cancel GL Entry ONLY if it exists (from Salary Slip)
        """
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

    def update_paid_amount_in_loan(self):
        """Update the paid amount in the loan document"""
        if self.against_loan:
            loan = frappe.get_doc("Loan", self.against_loan)

            total_paid = frappe.db.sql("""
                SELECT IFNULL(SUM(amount_paid), 0)
                FROM `tabLoan Repayment`
                WHERE against_loan = %s
                AND docstatus = 1
            """, self.against_loan)[0][0]

            loan.db_set("total_amount_paid", total_paid)

    def set_status_in_loan(self):
        """Update loan status based on payment"""
        if self.against_loan:
            from lending.loan_management.doctype.loan.loan import Loan
            loan = frappe.get_doc("Loan", self.against_loan)
            loan.set_status()
            loan.db_set("status", loan.status)

    def make_gl_entries(self, cancel=0, adv_adj=0):
        """
        ✅ Override to prevent GL Entry for manual Loan Repayments
        Only create GL Entry if from Salary Slip
        """
        if self.is_from_salary_slip():
            return super(CustomLoanRepayment, self).make_gl_entries(cancel=cancel, adv_adj=adv_adj)
        else:
            # Manual - skip GL Entry
            return None

    def is_from_salary_slip(self):
        """
        Check if this Loan Repayment was created from Salary Slip
        """
        if self.payroll_payable_account:
            return True

        salary_slip_loan = frappe.db.exists("Salary Slip Loan", {
            "loan_repayment_entry": self.name
        })
        if salary_slip_loan:
            return True

        return False


@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
    """
    ✅ Create Payment Entry from Loan Repayment
    ✅ يشتغل مع Salary Slip و Manual
    """

    def set_missing_values(source, target):
        loan_repayment = frappe.get_doc("Loan Repayment", source_name)

        # ✅ Validate: Loan Repayment must be submitted
        if loan_repayment.docstatus != 1:
            frappe.throw(
                _("لازم تعمل Submit للـ Loan Repayment الأول"))

        # ✅ التعديل الأساسي: نسمح بـ Payment Entry حتى لو من Salary Slip
        # بس نتأكد إنه مفيش Payment Entry موجود
        if loan_repayment.payment_entry:
            frappe.throw(
                _("في Payment Entry موجود فعلاً: {0}").format(
                    frappe.bold(loan_repayment.payment_entry)
                )
            )

        loan = frappe.get_doc("Loan", loan_repayment.against_loan)
        company = frappe.get_doc("Company", loan_repayment.company)

        # ✅ تحديد نوع الدفع حسب المصدر
        is_from_salary = loan_repayment.payroll_payable_account

        if is_from_salary:
            # من كشف المرتب: استلام من حساب المرتبات
            target.payment_type = "Receive"
            target.paid_from = loan_repayment.payroll_payable_account
            remarks_prefix = "استلام من المرتب"
        else:
            # Manual: استلام نقدي
            target.payment_type = "Receive"
            target.paid_from = loan.loan_account
            remarks_prefix = "سداد نقدي"

        # Payment Entry Configuration
        target.party_type = "Employee"
        target.party = loan.applicant
        target.paid_amount = loan_repayment.amount_paid
        target.received_amount = loan_repayment.amount_paid
        target.reference_no = loan_repayment.name
        target.reference_date = loan_repayment.posting_date
        target.company = loan_repayment.company
        target.mode_of_payment = "Cash"

        # ✅ Account Configuration
        # الحساب المستلم إليه (النقدية أو البنك)
        target.paid_to = company.default_cash_account or frappe.db.get_value(
            "Account",
            {"account_type": "Cash", "company": company.name, "is_group": 0},
            "name"
        )

        if not target.paid_to:
            frappe.throw(
                _("حدد حساب النقدية الافتراضي في الشركة {0}").format(company.name))

        target.paid_to_account_currency = company.default_currency
        target.paid_from_account_currency = company.default_currency

        # ✅ References
        target.append("references", {
            "reference_doctype": "Loan Repayment",
            "reference_name": loan_repayment.name,
            "total_amount": loan_repayment.amount_paid,
            "outstanding_amount": 0,
            "allocated_amount": 0
        })

        # ✅ Custom field
        if hasattr(target, 'loan_repayment'):
            target.loan_repayment = loan_repayment.name

        # Remarks
        target.remarks = (
            f"{remarks_prefix} للسلفة {loan.name} "
            f"للموظف {loan.applicant} - مبلغ {loan_repayment.amount_paid}"
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
    """
    ✅ API لجلب باقي المبلغ الكلي للقرض
    """
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
    """
    Get details of Loan Repayment for Payment Entry
    """
    doc = frappe.get_doc("Loan Repayment", loan_repayment)
    loan = frappe.get_doc("Loan", doc.against_loan)

    return {
        "employee": loan.applicant,
        "employee_name": frappe.db.get_value("Employee", loan.applicant, "employee_name"),
        "loan": doc.against_loan,
        "amount": doc.amount_paid,
        "loan_account": loan.loan_account,
        "posting_date": doc.posting_date,
        "from_salary_slip": bool(doc.payroll_payable_account)
    }
