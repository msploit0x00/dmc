# import frappe
# from frappe import _
# from frappe.utils import flt, getdate, nowdate
# from frappe.model.mapper import get_mapped_doc
# from lending.loan_management.doctype.loan_repayment.loan_repayment import LoanRepayment


# class CustomLoanRepayment(LoanRepayment):
#     """
#     Custom Loan Repayment Override
#     Purpose:
#     - From Salary Slip: Create GL Entry automatically
#     - Manual (after resignation): NO GL Entry (Payment Entry handles it)
#     - Update Repayment Schedule when manual payment is made
#     """

#     def on_submit(self):
#         """
#         ✅ Create GL Entry ONLY if from Salary Slip
#         ✅ Skip GL Entry if manual payment (after resignation)
#         ✅ Update Repayment Schedule for manual payments
#         """
#         if self.check_is_manual_payment():
#             # Manual payment after resignation
#             self.update_paid_amount_in_loan()
#             self.set_status_in_loan()
#             self.update_repayment_schedule_on_manual_payment()

#             frappe.msgprint(
#                 _("Loan Repayment submitted without GL Entry. Create Payment Entry to complete the transaction."),
#                 alert=True,
#                 indicator="blue"
#             )
#         else:
#             # From Salary Slip
#             super(CustomLoanRepayment, self).on_submit()
#             frappe.msgprint(
#                 _("Loan Repayment submitted. GL Entry created from Salary Slip."),
#                 alert=True,
#                 indicator="green"
#             )

#     def on_cancel(self):
#         """
#         ✅ Cancel GL Entry ONLY if it exists (from Salary Slip)
#         ✅ Revert Repayment Schedule for manual payments
#         """
#         has_gl_entry = frappe.db.exists("GL Entry", {
#             "voucher_type": "Loan Repayment",
#             "voucher_no": self.name,
#             "is_cancelled": 0
#         })

#         if has_gl_entry:
#             # From Salary Slip - call parent with error handling
#             try:
#                 super(CustomLoanRepayment, self).on_cancel()
#             except TypeError as e:
#                 # Handle NPA status update error from parent class
#                 if "update_all_linked_loan_customer_npa_status" in str(e):
#                     frappe.logger().warning(
#                         f"NPA status update error in parent on_cancel for {self.name}: {str(e)}"
#                     )
#                     # Try to update NPA status manually
#                     self.update_npa_status_on_cancel()
#                 else:
#                     raise
#         else:
#             # Manual payment
#             self.update_paid_amount_in_loan()
#             self.set_status_in_loan()
#             self.revert_repayment_schedule_on_cancel()
#             self.update_npa_status_on_cancel()

#         # unlink payment entry if exists
#         if self.payment_entry:
#             frappe.db.set_value("Loan Repayment", self.name,
#                                 "payment_entry", None)

#     def update_repayment_schedule_on_manual_payment(self):
#         """✅ Update Repayment Schedule when manual payment is made"""
#         if not self.against_loan:
#             return

#         try:
#             # ✅ Find active Loan Repayment Schedule for this loan
#             active_schedules = frappe.get_all(
#                 "Loan Repayment Schedule",
#                 filters={
#                     "loan": self.against_loan,
#                     "status": "Active",
#                     "docstatus": 1
#                 },
#                 fields=["name"],
#                 order_by="posting_date desc",
#                 limit=1
#             )

#             if not active_schedules:
#                 frappe.log_error(
#                     title=f"No Active Schedule for Loan {self.against_loan}",
#                     message=f"Loan Repayment {self.name} - No active schedule to update"
#                 )
#                 return

#             # Get the schedule document
#             schedule_doc = frappe.get_doc(
#                 "Loan Repayment Schedule", active_schedules[0].name)

#             if not hasattr(schedule_doc, "repayment_schedule") or not schedule_doc.repayment_schedule:
#                 frappe.log_error(
#                     title=f"No Repayment Rows in Schedule {schedule_doc.name}",
#                     message=f"Loan Repayment {self.name} - Schedule has no payment rows"
#                 )
#                 return

#             amount_to_allocate = flt(self.amount_paid)

#             # Sort by payment date
#             schedules = sorted(
#                 schedule_doc.repayment_schedule,
#                 key=lambda x: getdate(
#                     x.payment_date) if x.payment_date else getdate("1900-01-01")
#             )

#             for schedule_row in schedules:
#                 if amount_to_allocate <= 0:
#                     break

#                 paid_existing = flt(schedule_row.custom_paid_amount)
#                 total_due = flt(schedule_row.total_payment)

#                 if flt(paid_existing) >= total_due:
#                     continue

#                 paid_now = min(amount_to_allocate, total_due - paid_existing)

#                 # ✅ Update the child table row
#                 frappe.db.set_value(
#                     "Repayment Schedule",
#                     schedule_row.name,
#                     {
#                         "custom_paid_amount": paid_existing + paid_now,
#                         "custom_is_paid": 1 if (paid_existing + paid_now) >= total_due else 0,
#                         "custom_payment_reference": self.name,
#                         "custom_payment_date_actual": self.posting_date
#                     }
#                 )

#                 amount_to_allocate -= paid_now

#             frappe.db.commit()

#             frappe.msgprint(
#                 _("Repayment Schedule {0} updated for manual payment.").format(
#                     frappe.bold(schedule_doc.name)
#                 ),
#                 alert=True,
#                 indicator="green"
#             )

#         except Exception:
#             frappe.log_error(
#                 title=f"Error updating Repayment Schedule for {self.name}",
#                 message=frappe.get_traceback()
#             )
#             frappe.throw(
#                 _("Failed to update Repayment Schedule. Check Error Log."))

#     def revert_repayment_schedule_on_cancel(self):
#         """✅ Revert Repayment Schedule when cancelling manual payment"""
#         if not self.against_loan:
#             return

#         try:
#             # ✅ Find all schedules linked to this repayment
#             schedules = frappe.db.sql("""
#                 SELECT rs.name, rs.parent, rs.total_payment, rs.custom_paid_amount
#                 FROM `tabRepayment Schedule` rs
#                 WHERE rs.parenttype = 'Loan Repayment Schedule'
#                 AND rs.custom_payment_reference = %s
#             """, self.name, as_dict=1)

#             if not schedules:
#                 frappe.log_error(
#                     title=f"No schedules found for Loan Repayment {self.name}",
#                     message="Cannot revert schedule - no matching payment reference found"
#                 )
#                 return

#             for schedule in schedules:
#                 new_paid = max(
#                     0, flt(schedule.custom_paid_amount) - flt(self.amount_paid))

#                 frappe.db.set_value(
#                     "Repayment Schedule",
#                     schedule.name,
#                     {
#                         "custom_paid_amount": new_paid,
#                         "custom_is_paid": 1 if new_paid >= flt(schedule.total_payment) else 0,
#                         "custom_payment_reference": None,
#                         "custom_payment_date_actual": None
#                     }
#                 )

#             frappe.db.commit()

#             frappe.msgprint(
#                 _("Repayment Schedule reverted for cancelled payment."),
#                 alert=True,
#                 indicator="orange"
#             )

#         except Exception:
#             frappe.log_error(
#                 title=f"Error reverting Repayment Schedule for {self.name}",
#                 message=frappe.get_traceback()
#             )

#     def update_npa_status_on_cancel(self):
#         """
#         Update NPA status when cancelling loan repayments
#         Handles both old and new versions of the function
#         """
#         try:
#             from lending.loan_management.doctype.loan_repayment.loan_repayment import (
#                 update_all_linked_loan_customer_npa_status
#             )

#             # Try with posting_date first (newer version)
#             try:
#                 update_all_linked_loan_customer_npa_status(
#                     loan=self.against_loan,
#                     posting_date=self.posting_date
#                 )
#             except TypeError:
#                 # Fallback to older version without posting_date
#                 frappe.logger().info(
#                     f"Using legacy NPA status update for {self.name}"
#                 )
#                 update_all_linked_loan_customer_npa_status(
#                     loan=self.against_loan
#                 )

#         except Exception as e:
#             frappe.log_error(
#                 title=f"NPA Status Update Failed for {self.name}",
#                 message=frappe.get_traceback()
#             )

#     def make_gl_entries(self, cancel=0, adv_adj=0):
#         """✅ Prevent GL Entry for manual payments"""
#         if self.check_is_manual_payment():
#             frappe.logger().info(
#                 f"Skipping GL Entry for manual Loan Repayment {self.name}."
#             )
#             return None
#         return super(CustomLoanRepayment, self).make_gl_entries(cancel=cancel, adv_adj=adv_adj)

#     def validate(self):
#         super(CustomLoanRepayment, self).validate()

#         # ✅ Validate manual payment amount doesn't exceed remaining
#         if self.check_is_manual_payment() and self.against_loan:
#             # Get loan total
#             loan = frappe.get_doc("Loan", self.against_loan)

#             # ✅ Use loan.total_amount_paid (updated by system)
#             total_paid = flt(loan.total_amount_paid)
#             total_payable = flt(loan.total_payment)
#             remaining = total_payable - total_paid

#             # ✅ Check if amount exceeds remaining (with small tolerance for rounding)
#             if flt(self.amount_paid) > (remaining + 0.01):
#                 frappe.throw(
#                     _("Payment amount {0} exceeds remaining loan balance {1}.<br><br>"
#                       "Loan Total: {2}<br>"
#                       "Already Paid: {3}<br>"
#                       "Remaining: {4}<br><br>"
#                       "Please adjust the amount to {5} or less.").format(
#                         frappe.bold(frappe.format_value(
#                             self.amount_paid, {"fieldtype": "Currency"})),
#                         frappe.bold(frappe.format_value(
#                             remaining, {"fieldtype": "Currency"})),
#                         frappe.format_value(total_payable, {
#                                             "fieldtype": "Currency"}),
#                         frappe.format_value(
#                             total_paid, {"fieldtype": "Currency"}),
#                         frappe.format_value(
#                             remaining, {"fieldtype": "Currency"}),
#                         frappe.bold(frappe.format_value(
#                             remaining, {"fieldtype": "Currency"}))
#                     ),
#                     title=_("Overpayment Not Allowed")
#                 )

#         if self.payment_entry and self.docstatus == 0:
#             pe_status = frappe.db.get_value(
#                 "Payment Entry", self.payment_entry, "docstatus")
#             if pe_status == 1:
#                 frappe.msgprint(
#                     _("Linked Payment Entry {0} already submitted.").format(
#                         frappe.bold(self.payment_entry)
#                     ),
#                     alert=True,
#                     indicator="orange"
#                 )

#     def check_is_manual_payment(self):
#         """✅ Identify manual repayments"""
#         if flt(self.get("is_manual_payment")) == 1:
#             return True

#         if self.payroll_payable_account:
#             return False

#         if frappe.db.exists("Salary Slip Loan", {"loan_repayment_entry": self.name}):
#             return False

#         return True

#     def update_paid_amount_in_loan(self):
#         if self.against_loan:
#             total_paid = frappe.db.sql("""
#                 SELECT IFNULL(SUM(amount_paid), 0)
#                 FROM `tabLoan Repayment`
#                 WHERE against_loan = %s AND docstatus = 1
#             """, self.against_loan)[0][0]

#             frappe.db.set_value("Loan", self.against_loan,
#                                 "total_amount_paid", total_paid)

#     def set_status_in_loan(self):
#         if self.against_loan:
#             loan = frappe.get_doc("Loan", self.against_loan)
#             loan.set_status()
#             loan.db_set("status", loan.status)


# # ✅ Prevent Salary Slip from showing or deducting fully paid loans
# def prevent_duplicate_loan_deduction(doc, method):
#     """Hide loans that are not for this employee or already fully repaid."""
#     if not doc.employee:
#         return

#     # Get all active loans for this employee
#     active_loans = frappe.get_all(
#         "Loan",
#         filters={
#             "applicant": doc.employee,
#             "docstatus": 1,
#             "status": ["not in", ["Closed", "Fully Paid"]]
#         },
#         pluck="name"
#     )

#     # ✅ If no active loans → clear section
#     if not active_loans:
#         doc.set("loans", [])
#         doc.total_principal_amount = 0
#         doc.total_interest_amount = 0
#         doc.total_loan_repayment = 0

#         # ✅ Recalculate Net Pay after clearing loans
#         doc.calculate_net_pay()

#         # 🚫 Skip loan repayment entry
#         doc.flags.skip_loan_repayment_entry = True

#         frappe.msgprint(
#             _("No active loans for this employee — loan section will be hidden."),
#             alert=True,
#             indicator="blue"
#         )
#         return

#     # ✅ Filter valid loans only (not fully paid + has pending amount)
#     valid_rows = []
#     for row in doc.loans:
#         if row.loan not in active_loans:
#             continue

#         loan = frappe.get_doc("Loan", row.loan)

#         # Calculate total paid
#         total_paid = frappe.db.sql("""
#             SELECT IFNULL(SUM(amount_paid), 0)
#             FROM `tabLoan Repayment`
#             WHERE against_loan = %s AND docstatus = 1
#         """, row.loan)[0][0]

#         loan_total = loan.total_payment
#         remaining = flt(loan_total) - flt(total_paid)

#         # ✅ Loan fully paid
#         if remaining <= 0:
#             frappe.msgprint(
#                 _("Loan {0} is fully paid — removed from Salary Slip.").format(
#                     frappe.bold(row.loan)),
#                 alert=True,
#                 indicator="orange"
#             )
#             continue

#         # ✅ Adjust overpaid amounts
#         if flt(row.total_payment) > remaining:
#             frappe.msgprint(
#                 _("Loan {0}: Adjusted payment to remaining balance ({1}).").format(
#                     frappe.bold(row.loan),
#                     frappe.bold(frappe.format_value(
#                         remaining, {"fieldtype": "Currency"}))
#                 ),
#                 alert=True,
#                 indicator="orange"
#             )
#             row.total_payment = remaining
#             row.principal_amount = min(flt(row.principal_amount), remaining)
#             row.interest_amount = remaining - flt(row.principal_amount)

#         valid_rows.append(row)

#     # ✅ Update valid loans
#     doc.set("loans", valid_rows)

#     # ✅ If still no valid loans → clear again
#     if not valid_rows:
#         doc.set("loans", [])
#         doc.total_principal_amount = 0
#         doc.total_interest_amount = 0
#         doc.total_loan_repayment = 0
#         doc.calculate_net_pay()
#         doc.flags.skip_loan_repayment_entry = True

#         frappe.msgprint(
#             _("No active or unpaid loans to deduct — loan section will be hidden."),
#             alert=True,
#             indicator="blue"
#         )

# # ✅ Custom wrapper to skip loan repayment entry


# def custom_make_loan_repayment_entry(doc):
#     """
#     Custom wrapper to skip loan repayment entry
#     when the Salary Slip has no active loans.
#     """
#     from erpnext.payroll.doctype.salary_slip.salary_slip import make_loan_repayment_entry

#     if getattr(doc.flags, "skip_loan_repayment_entry", False):
#         frappe.msgprint(
#             _("Skipping Loan Repayment Entry — no active loans for this employee."),
#             alert=True,
#             indicator="blue"
#         )
#         return None

#     # Run normal ERPNext logic otherwise
#     return make_loan_repayment_entry(doc)


# # ==========================================
# # ✅ Whitelisted Functions للـ Client Script
# # ==========================================

# @frappe.whitelist()
# def get_remaining_loan_amount(loan_id):
#     """
#     ✅ حساب الباقي من القرض
#     يستخدم في Client Script لعرض المعلومات
#     """
#     if not loan_id:
#         frappe.throw(_("Loan ID is required"))

#     # Get loan document
#     loan = frappe.get_doc("Loan", loan_id)

#     # Calculate total paid
#     total_paid = frappe.db.sql("""
#         SELECT IFNULL(SUM(amount_paid), 0)
#         FROM `tabLoan Repayment`
#         WHERE against_loan = %s
#         AND docstatus = 1
#     """, loan_id)[0][0]

#     # Calculate remaining
#     total_payable = flt(loan.total_payment)
#     remaining = flt(total_payable) - flt(total_paid)

#     # ✅ Get currency from company (Loan doesn't have currency field)
#     company_currency = frappe.db.get_value(
#         "Company", loan.company, "default_currency")

#     return {
#         "total_payable": total_payable,
#         "total_paid": total_paid,
#         "remaining": max(0, remaining),  # ✅ لا يمكن أن يكون سالب
#         "currency": company_currency or frappe.defaults.get_global_default("currency")
#     }


# @frappe.whitelist()
# def make_payment_entry(source_name):
#     """
#     ✅ إنشاء Payment Entry من Loan Repayment
#     """
#     from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

#     loan_repayment = frappe.get_doc("Loan Repayment", source_name)

#     # ✅ التحقق من أن Payment Entry غير موجود
#     if loan_repayment.payment_entry:
#         frappe.throw(_("Payment Entry {0} already exists for this Loan Repayment").format(
#             frappe.bold(loan_repayment.payment_entry)
#         ))

#     # ✅ التحقق من أنه manual payment
#     if not loan_repayment.check_is_manual_payment():
#         frappe.throw(
#             _("Payment Entry can only be created for manual loan repayments (not from Salary Slip)"))

#     # Get loan document
#     loan = frappe.get_doc("Loan", loan_repayment.against_loan)

#     # ✅ Create Payment Entry manually
#     pe = frappe.new_doc("Payment Entry")
#     pe.payment_type = "Receive"
#     pe.posting_date = loan_repayment.posting_date or nowdate()
#     pe.company = loan.company

#     # Party details
#     pe.party_type = loan.applicant_type
#     pe.party = loan.applicant

#     # Amount
#     pe.paid_amount = flt(loan_repayment.amount_paid)
#     pe.received_amount = flt(loan_repayment.amount_paid)

#     # ✅ Accounts
#     # Paid To (Debit) - Cash/Bank Account
#     pe.paid_to = frappe.db.get_value(
#         "Company", loan.company, "default_cash_account")
#     if not pe.paid_to:
#         frappe.throw(
#             _("Please set Default Cash Account in Company {0}").format(loan.company))

#     pe.paid_to_account_currency = frappe.db.get_value(
#         "Account", pe.paid_to, "account_currency")

#     # Paid From (Credit) - Loan Account
#     pe.paid_from = loan.loan_account
#     pe.paid_from_account_currency = frappe.db.get_value(
#         "Account", loan.loan_account, "account_currency")

#     # Reference
#     pe.append("references", {
#         "reference_doctype": "Loan Repayment",
#         "reference_name": loan_repayment.name,
#         "allocated_amount": flt(loan_repayment.amount_paid)
#     })

#     # Link back to Loan Repayment
#     frappe.db.set_value("Loan Repayment", loan_repayment.name,
#                         "payment_entry", pe.name)

#     return pe.as_dict()


# @frappe.whitelist()
# def get_monthly_repayment_amount(loan_id):
#     """
#     ✅ حساب قيمة القسط الشهري من Loan Repayment Schedule
#     """
#     if not loan_id:
#         return 0

#     # Get latest active schedule
#     active_schedule = frappe.get_all(
#         "Loan Repayment Schedule",
#         filters={
#             "loan": loan_id,
#             "status": "Active",
#             "docstatus": 1
#         },
#         fields=["name"],
#         order_by="posting_date desc",
#         limit=1
#     )

#     if not active_schedule:
#         return 0

#     # Get first unpaid row
#     schedule_doc = frappe.get_doc(
#         "Loan Repayment Schedule", active_schedule[0].name)

#     for row in schedule_doc.repayment_schedule:
#         paid = flt(row.custom_paid_amount) if hasattr(
#             row, 'custom_paid_amount') else 0
#         total = flt(row.total_payment)

#         if paid < total:
#             # Return unpaid amount for this row
#             return total - paid

#     # All paid
#     return 0


import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from frappe.model.mapper import get_mapped_doc
from lending.loan_management.doctype.loan_repayment.loan_repayment import LoanRepayment


class CustomLoanRepayment(LoanRepayment):
    """
    Custom Loan Repayment Override
    Purpose:
    - From Salary Slip: Create GL Entry automatically
    - Manual (after resignation): NO GL Entry (Payment Entry handles it)
    - Update Repayment Schedule when manual payment is made
    """

    def on_submit(self):
        """
        ✅ Create GL Entry ONLY if from Salary Slip
        ✅ Skip GL Entry if manual payment (after resignation)
        ✅ Update Repayment Schedule for manual payments
        """
        if self.check_is_manual_payment():
            # Manual payment after resignation
            self.update_paid_amount_in_loan()
            self.set_status_in_loan()
            self.update_repayment_schedule_on_manual_payment()

            frappe.msgprint(
                _("Loan Repayment submitted without GL Entry. Create Payment Entry to complete the transaction."),
                alert=True,
                indicator="blue"
            )
        else:
            # From Salary Slip
            super(CustomLoanRepayment, self).on_submit()
            frappe.msgprint(
                _("Loan Repayment submitted. GL Entry created from Salary Slip."),
                alert=True,
                indicator="green"
            )

    def on_cancel(self):
        """
        ✅ Cancel GL Entry ONLY if it exists (from Salary Slip)
        ✅ Revert Repayment Schedule for manual payments
        """
        has_gl_entry = frappe.db.exists("GL Entry", {
            "voucher_type": "Loan Repayment",
            "voucher_no": self.name,
            "is_cancelled": 0
        })

        if has_gl_entry:
            # From Salary Slip - call parent with error handling
            try:
                super(CustomLoanRepayment, self).on_cancel()
            except TypeError as e:
                # Handle NPA status update error from parent class
                if "update_all_linked_loan_customer_npa_status" in str(e):
                    frappe.logger().warning(
                        f"NPA status update error in parent on_cancel for {self.name}: {str(e)}"
                    )
                    # Try to update NPA status manually
                    self.update_npa_status_on_cancel()
                else:
                    raise
        else:
            # Manual payment
            self.update_paid_amount_in_loan()
            self.set_status_in_loan()
            self.revert_repayment_schedule_on_cancel()
            self.update_npa_status_on_cancel()

        # unlink payment entry if exists
        if self.payment_entry:
            frappe.db.set_value("Loan Repayment", self.name,
                                "payment_entry", None)

    def update_repayment_schedule_on_manual_payment(self):
        """✅ Update Repayment Schedule when manual payment is made"""
        if not self.against_loan:
            return

        try:
            # ✅ Find active Loan Repayment Schedule for this loan
            active_schedules = frappe.get_all(
                "Loan Repayment Schedule",
                filters={
                    "loan": self.against_loan,
                    "status": "Active",
                    "docstatus": 1
                },
                fields=["name"],
                order_by="posting_date desc",
                limit=1
            )

            if not active_schedules:
                frappe.log_error(
                    title=f"No Active Schedule for Loan {self.against_loan}",
                    message=f"Loan Repayment {self.name} - No active schedule to update"
                )
                return

            # Get the schedule document
            schedule_doc = frappe.get_doc(
                "Loan Repayment Schedule", active_schedules[0].name)

            if not hasattr(schedule_doc, "repayment_schedule") or not schedule_doc.repayment_schedule:
                frappe.log_error(
                    title=f"No Repayment Rows in Schedule {schedule_doc.name}",
                    message=f"Loan Repayment {self.name} - Schedule has no payment rows"
                )
                return

            amount_to_allocate = flt(self.amount_paid)

            # Sort by payment date
            schedules = sorted(
                schedule_doc.repayment_schedule,
                key=lambda x: getdate(
                    x.payment_date) if x.payment_date else getdate("1900-01-01")
            )

            for schedule_row in schedules:
                if amount_to_allocate <= 0:
                    break

                paid_existing = flt(schedule_row.custom_paid_amount)
                total_due = flt(schedule_row.total_payment)

                if flt(paid_existing) >= total_due:
                    continue

                paid_now = min(amount_to_allocate, total_due - paid_existing)

                # ✅ Update the child table row
                frappe.db.set_value(
                    "Repayment Schedule",
                    schedule_row.name,
                    {
                        "custom_paid_amount": paid_existing + paid_now,
                        "custom_is_paid": 1 if (paid_existing + paid_now) >= total_due else 0,
                        "custom_payment_reference": self.name,
                        "custom_payment_date_actual": self.posting_date
                    }
                )

                amount_to_allocate -= paid_now

            frappe.db.commit()

            frappe.msgprint(
                _("Repayment Schedule {0} updated for manual payment.").format(
                    frappe.bold(schedule_doc.name)
                ),
                alert=True,
                indicator="green"
            )

        except Exception:
            frappe.log_error(
                title=f"Error updating Repayment Schedule for {self.name}",
                message=frappe.get_traceback()
            )
            frappe.throw(
                _("Failed to update Repayment Schedule. Check Error Log."))

    def revert_repayment_schedule_on_cancel(self):
        """✅ Revert Repayment Schedule when cancelling manual payment"""
        if not self.against_loan:
            return

        try:
            # ✅ Find all schedules linked to this repayment
            schedules = frappe.db.sql("""
                SELECT rs.name, rs.parent, rs.total_payment, rs.custom_paid_amount
                FROM `tabRepayment Schedule` rs
                WHERE rs.parenttype = 'Loan Repayment Schedule'
                AND rs.custom_payment_reference = %s
            """, self.name, as_dict=1)

            if not schedules:
                frappe.log_error(
                    title=f"No schedules found for Loan Repayment {self.name}",
                    message="Cannot revert schedule - no matching payment reference found"
                )
                return

            for schedule in schedules:
                new_paid = max(
                    0, flt(schedule.custom_paid_amount) - flt(self.amount_paid))

                frappe.db.set_value(
                    "Repayment Schedule",
                    schedule.name,
                    {
                        "custom_paid_amount": new_paid,
                        "custom_is_paid": 1 if new_paid >= flt(schedule.total_payment) else 0,
                        "custom_payment_reference": None,
                        "custom_payment_date_actual": None
                    }
                )

            frappe.db.commit()

            frappe.msgprint(
                _("Repayment Schedule reverted for cancelled payment."),
                alert=True,
                indicator="orange"
            )

        except Exception:
            frappe.log_error(
                title=f"Error reverting Repayment Schedule for {self.name}",
                message=frappe.get_traceback()
            )

    def update_npa_status_on_cancel(self):
        """
        Update NPA status when cancelling loan repayments
        Handles both old and new versions of the function
        """
        try:
            from lending.loan_management.doctype.loan_repayment.loan_repayment import (
                update_all_linked_loan_customer_npa_status
            )

            # Try with posting_date first (newer version)
            try:
                update_all_linked_loan_customer_npa_status(
                    loan=self.against_loan,
                    posting_date=self.posting_date
                )
            except TypeError:
                # Fallback to older version without posting_date
                frappe.logger().info(
                    f"Using legacy NPA status update for {self.name}"
                )
                update_all_linked_loan_customer_npa_status(
                    loan=self.against_loan
                )

        except Exception as e:
            frappe.log_error(
                title=f"NPA Status Update Failed for {self.name}",
                message=frappe.get_traceback()
            )

    def make_gl_entries(self, cancel=0, adv_adj=0):
        """✅ Prevent GL Entry for manual payments"""
        if self.check_is_manual_payment():
            frappe.logger().info(
                f"Skipping GL Entry for manual Loan Repayment {self.name}."
            )
            return None
        return super(CustomLoanRepayment, self).make_gl_entries(cancel=cancel, adv_adj=adv_adj)

    def validate(self):
        super(CustomLoanRepayment, self).validate()

        # ✅ Validate manual payment amount doesn't exceed remaining
        if self.check_is_manual_payment() and self.against_loan:
            # Get loan total
            loan = frappe.get_doc("Loan", self.against_loan)

            # ✅ Use loan.total_amount_paid (updated by system)
            total_paid = flt(loan.total_amount_paid)
            total_payable = flt(loan.total_payment)
            remaining = total_payable - total_paid

            # ✅ Check if amount exceeds remaining (with small tolerance for rounding)
            if flt(self.amount_paid) > (remaining + 0.01):
                frappe.throw(
                    _("Payment amount {0} exceeds remaining loan balance {1}.<br><br>"
                      "Loan Total: {2}<br>"
                      "Already Paid: {3}<br>"
                      "Remaining: {4}<br><br>"
                      "Please adjust the amount to {5} or less.").format(
                        frappe.bold(frappe.format_value(
                            self.amount_paid, {"fieldtype": "Currency"})),
                        frappe.bold(frappe.format_value(
                            remaining, {"fieldtype": "Currency"})),
                        frappe.format_value(total_payable, {
                                            "fieldtype": "Currency"}),
                        frappe.format_value(
                            total_paid, {"fieldtype": "Currency"}),
                        frappe.format_value(
                            remaining, {"fieldtype": "Currency"}),
                        frappe.bold(frappe.format_value(
                            remaining, {"fieldtype": "Currency"}))
                    ),
                    title=_("Overpayment Not Allowed")
                )

        if self.payment_entry and self.docstatus == 0:
            pe_status = frappe.db.get_value(
                "Payment Entry", self.payment_entry, "docstatus")
            if pe_status == 1:
                frappe.msgprint(
                    _("Linked Payment Entry {0} already submitted.").format(
                        frappe.bold(self.payment_entry)
                    ),
                    alert=True,
                    indicator="orange"
                )

    def check_is_manual_payment(self):
        """✅ Identify manual repayments"""
        if flt(self.get("is_manual_payment")) == 1:
            return True

        if self.payroll_payable_account:
            return False

        if frappe.db.exists("Salary Slip Loan", {"loan_repayment_entry": self.name}):
            return False

        return True

    def update_paid_amount_in_loan(self):
        if self.against_loan:
            total_paid = frappe.db.sql("""
                SELECT IFNULL(SUM(amount_paid), 0)
                FROM `tabLoan Repayment`
                WHERE against_loan = %s AND docstatus = 1
            """, self.against_loan)[0][0]

            frappe.db.set_value("Loan", self.against_loan,
                                "total_amount_paid", total_paid)

    def set_status_in_loan(self):
        if self.against_loan:
            loan = frappe.get_doc("Loan", self.against_loan)
            loan.set_status()
            loan.db_set("status", loan.status)


# ========================================
# 🔥 التعديل الأول: Logging محسّن + Flag جديد
# ========================================
def prevent_duplicate_loan_deduction(doc, method):
    """Hide loans that are not for this employee or already fully repaid."""
    if not doc.employee:
        return

    # Get all active loans for this employee
    active_loans = frappe.get_all(
        "Loan",
        filters={
            "applicant": doc.employee,
            "docstatus": 1,
            "status": ["not in", ["Closed", "Fully Paid"]]
        },
        pluck="name"
    )

    # ✅ If no active loans → clear section
    if not active_loans:
        doc.set("loans", [])
        doc.total_principal_amount = 0
        doc.total_interest_amount = 0
        doc.total_loan_repayment = 0

        # ✅ Recalculate Net Pay after clearing loans
        doc.calculate_net_pay()

        # 🚫 CRITICAL: Skip loan repayment entry
        doc.flags.skip_loan_repayment_entry = True

        # ✅ 🔥 جديد: Mark that we cleaned the loans
        doc.flags.loans_cleaned = True

        # 🔥 جديد: Logging محسّن
        frappe.logger().info(
            f"🚫 Salary Slip {doc.name}: No active loans - skip_loan_repayment_entry = True"
        )

        return

    # ✅ Filter valid loans only (not fully paid + has pending amount)
    valid_rows = []
    has_fully_paid_loans = False

    for row in doc.loans:
        if row.loan not in active_loans:
            continue

        loan = frappe.get_doc("Loan", row.loan)

        # Calculate total paid
        total_paid = frappe.db.sql("""
            SELECT IFNULL(SUM(amount_paid), 0)
            FROM `tabLoan Repayment`
            WHERE against_loan = %s AND docstatus = 1
        """, row.loan)[0][0]

        loan_total = loan.total_payment
        remaining = flt(loan_total) - flt(total_paid)

        # ✅ Loan fully paid
        if remaining <= 0:
            has_fully_paid_loans = True
            frappe.msgprint(
                _("Loan {0} is fully paid — removed from Salary Slip.").format(
                    frappe.bold(row.loan)),
                alert=True,
                indicator="orange"
            )
            continue

        # ✅ Adjust overpaid amounts
        if flt(row.total_payment) > remaining:
            frappe.msgprint(
                _("Loan {0}: Adjusted payment to remaining balance ({1}).").format(
                    frappe.bold(row.loan),
                    frappe.bold(frappe.format_value(
                        remaining, {"fieldtype": "Currency"}))
                ),
                alert=True,
                indicator="orange"
            )
            row.total_payment = remaining
            row.principal_amount = min(flt(row.principal_amount), remaining)
            row.interest_amount = remaining - flt(row.principal_amount)

        valid_rows.append(row)

    # ✅ Update valid loans
    doc.set("loans", valid_rows)

    # ✅ If no valid loans remain → clear and skip repayment
    if not valid_rows:
        doc.set("loans", [])
        doc.total_principal_amount = 0
        doc.total_interest_amount = 0
        doc.total_loan_repayment = 0
        doc.calculate_net_pay()

        # 🚫 CRITICAL: Skip loan repayment entry
        doc.flags.skip_loan_repayment_entry = True
        doc.flags.loans_cleaned = True

        # 🔥 جديد: Logging محسّن
        frappe.logger().info(
            f"🚫 Salary Slip {doc.name}: All loans fully paid - skip_loan_repayment_entry = True"
        )

        frappe.msgprint(
            _("No active or unpaid loans to deduct — loan section will be hidden."),
            alert=True,
            indicator="blue"
        )
    else:
        # ✅ 🔥 جديد: Has valid loans - allow repayment entry
        doc.flags.skip_loan_repayment_entry = False
        doc.flags.loans_cleaned = False

        frappe.logger().info(
            f"✅ Salary Slip {doc.name}: Has {len(valid_rows)} active loans - will create repayment entry"
        )


# ========================================
# 🔥 التعديل الثاني: Check مزدوج + Logging
# ========================================
def custom_make_loan_repayment_entry(doc):
    """
    Custom wrapper to skip loan repayment entry
    when the Salary Slip has no active loans.
    """
    # ✅ 🔥 جديد: CRITICAL CHECK: Skip if flag is set
    if getattr(doc.flags, "skip_loan_repayment_entry", False):
        frappe.logger().info(
            f"🚫 Skipping Loan Repayment Entry for Salary Slip {doc.name} - "
            f"No active loans or all loans fully paid"
        )

        # Show message only once (not on every hook call)
        if not getattr(doc.flags, "skip_message_shown", False):
            frappe.msgprint(
                _("No Loan Repayment Entry created - employee has no active unpaid loans."),
                alert=True,
                indicator="blue"
            )
            doc.flags.skip_message_shown = True

        return None

    # ✅ 🔥 جديد: Check if loans table is empty
    if not doc.get("loans") or len(doc.loans) == 0:
        frappe.logger().info(
            f"🚫 Skipping Loan Repayment Entry for Salary Slip {doc.name} - "
            f"loans table is empty"
        )
        return None

    # ✅ 🔥 جديد: Run normal ERPNext logic with logging
    frappe.logger().info(
        f"✅ Creating Loan Repayment Entry for Salary Slip {doc.name} - "
        f"Has {len(doc.loans)} active loan(s)"
    )

    from erpnext.payroll.doctype.salary_slip.salary_slip import make_loan_repayment_entry
    return make_loan_repayment_entry(doc)
