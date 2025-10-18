# import frappe
# from frappe import _
# from frappe.utils import flt, getdate
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
#             super(CustomLoanRepayment, self).on_cancel()
#         else:
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
#             loan = frappe.get_doc("Loan", self.against_loan)
#             if not hasattr(loan, "repayment_schedule") or not loan.repayment_schedule:
#                 frappe.log_error(
#                     title=f"No Repayment Schedule for Loan {self.against_loan}",
#                     message=f"Loan Repayment {self.name} - No schedule to update"
#                 )
#                 return

#             amount_to_allocate = flt(self.amount_paid)

#             schedules = sorted(
#                 loan.repayment_schedule,
#                 key=lambda x: getdate(
#                     x.payment_date) if x.payment_date else getdate("1900-01-01")
#             )

#             for schedule in schedules:
#                 if amount_to_allocate <= 0:
#                     break

#                 paid_existing = flt(schedule.custom_paid_amount)
#                 total_due = flt(schedule.total_payment)

#                 if flt(paid_existing) >= total_due:
#                     continue

#                 paid_now = min(amount_to_allocate, total_due - paid_existing)

#                 frappe.db.set_value(
#                     "Repayment Schedule",
#                     schedule.name,
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
#                 _("Repayment Schedule updated for manual payment."),
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
#             schedules = frappe.get_all(
#                 "Loan Repayment Schedule",
#                 filters={
#                     "loan": self.against_loan,
#                     "custom_payment_reference": self.name
#                 },
#                 fields=["name", "total_payment", "custom_paid_amount"]
#             )

#             for schedule in schedules:
#                 new_paid = max(
#                     0, flt(schedule.custom_paid_amount) - flt(self.amount_paid))
#                 frappe.db.set_value(
#                     "Loan Repayment Schedule",
#                     schedule.name,
#                     {
#                         "custom_paid_amount": new_paid,
#                         "custom_is_paid": 1 if new_paid >= flt(schedule.total_payment) else 0,
#                         "custom_payment_reference": None,
#                         "custom_payment_date_actual": None
#                     }
#                 )

#             frappe.db.commit()

#         except Exception:
#             frappe.log_error(
#                 title=f"Error reverting Repayment Schedule for {self.name}",
#                 message=frappe.get_traceback()
#             )

#     def update_npa_status_on_cancel(self):
#         try:
#             from lending.loan_management.doctype.loan_repayment.loan_repayment import (
#                 update_all_linked_loan_customer_npa_status
#             )
#             update_all_linked_loan_customer_npa_status(
#                 loan=self.against_loan, posting_date=self.posting_date
#             )
#         except Exception as e:
#             frappe.log_error(
#                 f"NPA Status Update Failed for {self.name}", str(e))

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


# # # ✅ Prevent Salary Slip from showing or deducting fully paid loans
# # def prevent_duplicate_loan_deduction(doc, method):
# #     """Hide loans that are not for this employee or already fully repaid."""
# #     if not doc.employee:
# #         return

# #     # Get all active loans for this employee
# #     active_loans = frappe.get_all(
# #         "Loan",
# #         filters={
# #             "applicant": doc.employee,
# #             "docstatus": 1,
# #             "status": ["not in", ["Closed", "Fully Paid"]]
# #         },
# #         pluck="name"
# #     )

# #     # ✅ If no active loans → clear section and set flag
# #     if not active_loans:
# #         doc.set("loans", [])
# #         doc.total_principal_amount = 0
# #         doc.total_interest_amount = 0
# #         doc.total_loan_repayment = 0

# #         # 🚫 Tell system to skip make_loan_repayment_entry later
# #         doc.flags.skip_loan_repayment_entry = True

# #         frappe.msgprint(
# #             _("No active loans for this employee — hiding Loan Repayment section."),
# #             alert=True,
# #             indicator="blue"
# #         )
# #         return

# #     # ✅ Filter valid loans only (not fully paid)
# #     valid_rows = []
# #     for row in doc.loans:
# #         if row.loan in active_loans:
# #             total_paid = frappe.db.sql("""
# #                 SELECT IFNULL(SUM(amount_paid), 0)
# #                 FROM `tabLoan Repayment`
# #                 WHERE against_loan = %s AND docstatus = 1
# #             """, row.loan)[0][0]

# #             loan_total = frappe.db.get_value("Loan", row.loan, "total_payment")

# #             if flt(total_paid) < flt(loan_total):
# #                 valid_rows.append(row)
# #             else:
# #                 frappe.msgprint(
# #                     _("Loan {0} is fully paid — it will be removed from Salary Slip.").format(
# #                         frappe.bold(row.loan)
# #                     ),
# #                     alert=True,
# #                     indicator="orange"
# #                 )

# #     doc.set("loans", valid_rows)

# #     # ✅ Still empty → hide and set flag
# #     if not valid_rows:
# #         doc.set("loans", [])
# #         doc.total_principal_amount = 0
# #         doc.total_interest_amount = 0
# #         doc.total_loan_repayment = 0
# #         doc.flags.skip_loan_repayment_entry = True

# #         frappe.msgprint(
# #             _("No active or unpaid loans to deduct — hiding Loan Repayment section."),
# #             alert=True,
# #             indicator="blue"
# #         )


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

#     # ✅ If no active loans → clear section and set flag
#     if not active_loans:
#         doc.set("loans", [])
#         doc.total_principal_amount = 0
#         doc.total_interest_amount = 0
#         doc.total_loan_repayment = 0

#         # ✅ CRITICAL: Recalculate Net Pay after clearing loans
#         doc.calculate_net_pay()

#         # 🚫 Tell system to skip make_loan_repayment_entry later
#         doc.flags.skip_loan_repayment_entry = True

#         frappe.msgprint(
#             _("No active loans for this employee — hiding Loan Repayment section."),
#             alert=True,
#             indicator="blue"
#         )
#         return

#     # ✅ Filter valid loans only (not fully paid)
#     valid_rows = []
#     for row in doc.loans:
#         if row.loan in active_loans:
#             total_paid = frappe.db.sql("""
#                 SELECT IFNULL(SUM(amount_paid), 0)
#                 FROM `tabLoan Repayment`
#                 WHERE against_loan = %s AND docstatus = 1
#             """, row.loan)[0][0]

#             loan_total = frappe.db.get_value("Loan", row.loan, "total_payment")

#             if flt(total_paid) < flt(loan_total):
#                 valid_rows.append(row)
#             else:
#                 frappe.msgprint(
#                     _("Loan {0} is fully paid — it will be removed from Salary Slip.").format(
#                         frappe.bold(row.loan)
#                     ),
#                     alert=True,
#                     indicator="orange"
#                 )

#     doc.set("loans", valid_rows)

#     # ✅ Still empty → hide and set flag
#     if not valid_rows:
#         doc.set("loans", [])
#         doc.total_principal_amount = 0
#         doc.total_interest_amount = 0
#         doc.total_loan_repayment = 0

#         # ✅ CRITICAL: Recalculate Net Pay after clearing loans
#         doc.calculate_net_pay()

#         doc.flags.skip_loan_repayment_entry = True

#         frappe.msgprint(
#             _("No active or unpaid loans to deduct — hiding Loan Repayment section."),
#             alert=True,
#             indicator="blue"
#         )
import frappe
from frappe import _
from frappe.utils import flt, getdate
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
            loan = frappe.get_doc("Loan", self.against_loan)
            if not hasattr(loan, "repayment_schedule") or not loan.repayment_schedule:
                frappe.log_error(
                    title=f"No Repayment Schedule for Loan {self.against_loan}",
                    message=f"Loan Repayment {self.name} - No schedule to update"
                )
                return

            amount_to_allocate = flt(self.amount_paid)

            schedules = sorted(
                loan.repayment_schedule,
                key=lambda x: getdate(
                    x.payment_date) if x.payment_date else getdate("1900-01-01")
            )

            for schedule in schedules:
                if amount_to_allocate <= 0:
                    break

                paid_existing = flt(schedule.custom_paid_amount)
                total_due = flt(schedule.total_payment)

                if flt(paid_existing) >= total_due:
                    continue

                paid_now = min(amount_to_allocate, total_due - paid_existing)

                frappe.db.set_value(
                    "Repayment Schedule",
                    schedule.name,
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
                _("Repayment Schedule updated for manual payment."),
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
            schedules = frappe.get_all(
                "Loan Repayment Schedule",
                filters={
                    "loan": self.against_loan,
                    "custom_payment_reference": self.name
                },
                fields=["name", "total_payment", "custom_paid_amount"]
            )

            for schedule in schedules:
                new_paid = max(
                    0, flt(schedule.custom_paid_amount) - flt(self.amount_paid))
                frappe.db.set_value(
                    "Loan Repayment Schedule",
                    schedule.name,
                    {
                        "custom_paid_amount": new_paid,
                        "custom_is_paid": 1 if new_paid >= flt(schedule.total_payment) else 0,
                        "custom_payment_reference": None,
                        "custom_payment_date_actual": None
                    }
                )

            frappe.db.commit()

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
            # Get total already paid
            total_paid = frappe.db.sql("""
                SELECT IFNULL(SUM(amount_paid), 0)
                FROM `tabLoan Repayment`
                WHERE against_loan = %s 
                AND docstatus = 1
                AND name != %s
            """, (self.against_loan, self.name))[0][0]

            # Get loan total
            loan = frappe.get_doc("Loan", self.against_loan)
            remaining = flt(loan.total_payment) - flt(total_paid)

            # Check if amount exceeds remaining
            if flt(self.amount_paid) > remaining:
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
                        frappe.format_value(loan.total_payment, {
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


# ✅ Prevent Salary Slip from showing or deducting fully paid loans
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

    # ✅ If no active loans → clear section and set flag
    if not active_loans:
        doc.set("loans", [])
        doc.total_principal_amount = 0
        doc.total_interest_amount = 0
        doc.total_loan_repayment = 0

        # ✅ CRITICAL: Recalculate Net Pay after clearing loans
        doc.calculate_net_pay()

        # 🚫 Tell system to skip make_loan_repayment_entry later
        doc.flags.skip_loan_repayment_entry = True

        # ✅ Pass flag to client side for hiding section
        if not doc.get("__onload"):
            doc.set_onload("hide_loan_section", True)
        else:
            doc.__onload.hide_loan_section = True

        frappe.msgprint(
            _("No active loans for this employee — hiding Loan Repayment section."),
            alert=True,
            indicator="blue"
        )
        return

    # ✅ Filter valid loans only (not fully paid + has pending amount)
    valid_rows = []
    for row in doc.loans:
        if row.loan not in active_loans:
            continue

        # Get loan details
        loan = frappe.get_doc("Loan", row.loan)

        # Calculate total paid
        total_paid = frappe.db.sql("""
            SELECT IFNULL(SUM(amount_paid), 0)
            FROM `tabLoan Repayment`
            WHERE against_loan = %s AND docstatus = 1
        """, row.loan)[0][0]

        loan_total = loan.total_payment
        remaining = flt(loan_total) - flt(total_paid)

        # ✅ Check if loan is fully paid
        if remaining <= 0:
            frappe.msgprint(
                _("Loan {0} is fully paid (Total: {1}, Paid: {2}) — removed from Salary Slip.").format(
                    frappe.bold(row.loan),
                    frappe.bold(frappe.format_value(
                        loan_total, {"fieldtype": "Currency"})),
                    frappe.bold(frappe.format_value(
                        total_paid, {"fieldtype": "Currency"}))
                ),
                alert=True,
                indicator="orange"
            )
            continue

        # ✅ Check if amount in row exceeds remaining
        if flt(row.total_payment) > remaining:
            frappe.msgprint(
                _("Loan {0}: Adjusted payment from {1} to {2} (Remaining balance)").format(
                    frappe.bold(row.loan),
                    frappe.bold(frappe.format_value(
                        row.total_payment, {"fieldtype": "Currency"})),
                    frappe.bold(frappe.format_value(
                        remaining, {"fieldtype": "Currency"}))
                ),
                alert=True,
                indicator="orange"
            )
            # Adjust the amounts
            row.total_payment = remaining
            row.principal_amount = min(flt(row.principal_amount), remaining)
            row.interest_amount = remaining - flt(row.principal_amount)

        # ✅ Add to valid rows
        valid_rows.append(row)

    doc.set("loans", valid_rows)

    # ✅ Still empty → hide and set flag
    if not valid_rows:
        doc.set("loans", [])
        doc.total_principal_amount = 0
        doc.total_interest_amount = 0
        doc.total_loan_repayment = 0

        # ✅ CRITICAL: Recalculate Net Pay after clearing loans
        doc.calculate_net_pay()

        doc.flags.skip_loan_repayment_entry = True

        # ✅ Pass flag to client side for hiding section
        if not doc.get("__onload"):
            doc.set_onload("hide_loan_section", True)
        else:
            doc.__onload.hide_loan_section = True

        frappe.msgprint(
            _("No active or unpaid loans to deduct — hiding Loan Repayment section."),
            alert=True,
            indicator="blue"
        )


# ✅ Custom wrapper to skip loan repayment entry
def custom_make_loan_repayment_entry(doc):
    """
    Custom wrapper to skip loan repayment entry
    when the Salary Slip has no active loans.
    """
    from erpnext.payroll.doctype.salary_slip.salary_slip import make_loan_repayment_entry

    if getattr(doc.flags, "skip_loan_repayment_entry", False):
        frappe.msgprint(
            _("Skipping Loan Repayment Entry — no active loans for this employee."),
            alert=True,
            indicator="blue"
        )
        return None

    # Run normal ERPNext logic otherwise
    return make_loan_repayment_entry(doc)
