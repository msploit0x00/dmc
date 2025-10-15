# import frappe
# from frappe import _
# from frappe.model.mapper import get_mapped_doc
# from lending.loan_management.doctype.loan_repayment.loan_repayment import LoanRepayment


# class CustomLoanRepayment(LoanRepayment):
#     """
#     Custom Loan Repayment Override
#     Purpose:
#     - From Salary Slip: Create GL Entry automatically
#     - Manual (after resignation): NO GL Entry (Payment Entry handles it)
#     """

#     def on_submit(self):
#         """
#         ✅ Create GL Entry ONLY if from Salary Slip
#         ✅ Skip GL Entry if manual payment (after resignation)
#         """
#         if self.check_is_manual_payment():
#             # Manual payment after resignation - NO GL Entry
#             # Only update loan status
#             self.update_paid_amount_in_loan()
#             self.set_status_in_loan()

#             frappe.msgprint(
#                 _("Loan Repayment submitted without GL Entry. Create Payment Entry to complete the transaction."),
#                 alert=True,
#                 indicator="blue"
#             )
#         else:
#             # From Salary Slip - create GL Entry (Core behavior)
#             super(CustomLoanRepayment, self).on_submit()
#             frappe.msgprint(
#                 _("Loan Repayment submitted. GL Entry created from Salary Slip."),
#                 alert=True,
#                 indicator="green"
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
#             # Manual - just update loan status manually
#             self.update_paid_amount_in_loan()
#             self.set_status_in_loan()

#             # Update NPA status for all linked loan customers
#             self.update_npa_status_on_cancel()

#         # Unlink Payment Entry if exists
#         if self.payment_entry:
#             frappe.db.set_value("Loan Repayment", self.name,
#                                 "payment_entry", None)

#     def update_npa_status_on_cancel(self):
#         """
#         Update NPA status when cancelling manual loan repayments
#         This replicates the parent class behavior for NPA updates
#         """
#         try:
#             # Import the function from lending module
#             from lending.loan_management.doctype.loan_repayment.loan_repayment import (
#                 update_all_linked_loan_customer_npa_status
#             )

#             # Call with the posting_date argument
#             update_all_linked_loan_customer_npa_status(
#                 loan=self.against_loan,
#                 posting_date=self.posting_date
#             )
#         except Exception as e:
#             frappe.log_error(
#                 title=f"NPA Status Update Failed for {self.name}",
#                 message=str(e)
#             )

#     def make_gl_entries(self, cancel=0, adv_adj=0):
#         """
#         ✅ CRITICAL: Override to prevent GL Entry for manual payments
#         """
#         if self.check_is_manual_payment():
#             # Manual payment - Skip GL Entry completely
#             frappe.logger().info(
#                 f"Skipping GL Entry for manual Loan Repayment {self.name}. "
#                 f"GL Entry will be created via Payment Entry."
#             )
#             return None

#         # From Salary Slip - create GL Entry (Core behavior)
#         return super(CustomLoanRepayment, self).make_gl_entries(cancel=cancel, adv_adj=adv_adj)

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

#     def check_is_manual_payment(self):
#         """
#         ✅ Check if this is a manual payment (after resignation)

#         Returns: True if manual payment, False if from Salary Slip

#         Logic:
#         1. Check custom field 'is_manual_payment' (user explicitly marks it)
#         2. If not set, check if payroll_payable_account exists (from Salary Slip)
#         """
#         # Method 1: Check custom field (explicitly marked as manual)
#         # Use get() to safely access the field value
#         manual_payment_flag = self.get('is_manual_payment')
#         if manual_payment_flag and int(manual_payment_flag) == 1:
#             return True

#         # Method 2: If payroll_payable_account exists = from Salary Slip
#         if self.payroll_payable_account:
#             return False

#         # Method 3: Check if linked to Salary Slip
#         salary_slip_loan = frappe.db.exists("Salary Slip Loan", {
#             "loan_repayment_entry": self.name
#         })
#         if salary_slip_loan:
#             return False

#         # Default: If no payroll account and not from salary slip = assume manual
#         # This handles the case where user forgets to check the box
#         return True

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


# @frappe.whitelist()
# def make_payment_entry(source_name, target_doc=None):
#     """
#     Create Payment Entry from Loan Repayment
#     ✅ This creates the GL Entry for manual payments
#     """

#     def set_missing_values(source, target):
#         loan_repayment = frappe.get_doc("Loan Repayment", source_name)

#         # ✅ Validate: Loan Repayment must be submitted
#         if loan_repayment.docstatus != 1:
#             frappe.throw(
#                 _("Loan Repayment must be submitted before creating Payment Entry"))

#         # ✅ Check if Payment Entry already exists
#         if loan_repayment.payment_entry:
#             frappe.throw(
#                 _("Payment Entry {0} already exists for this Loan Repayment").format(
#                     frappe.bold(loan_repayment.payment_entry)
#                 )
#             )

#         # ✅ Don't allow Payment Entry for Salary Slip repayments
#         manual_payment_flag = loan_repayment.get('is_manual_payment')
#         is_manual = manual_payment_flag and int(manual_payment_flag) == 1

#         if loan_repayment.payroll_payable_account and not is_manual:
#             frappe.throw(
#                 _("Cannot create Payment Entry for Loan Repayment from Salary Slip. "
#                   "GL Entry is already created via Salary Slip accounting.")
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
#         # This creates THE GL Entry:
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
#                 _("Please set Default Cash Account in Company {0}").format(
#                     company.name)
#             )

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
#             f"Manual payment received for Loan Repayment {loan_repayment.name} "
#             f"against Loan {loan.name} for Employee {loan.applicant} (After Resignation)"
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
# def get_remaining_loan_amount(loan_id):
#     """Get remaining loan amount for early settlement"""
#     loan = frappe.get_doc("Loan", loan_id)

#     total_payable = loan.total_payment

#     total_paid = frappe.db.sql("""
#         SELECT IFNULL(SUM(amount_paid), 0)
#         FROM `tabLoan Repayment`
#         WHERE against_loan = %s
#         AND docstatus = 1
#     """, loan_id)[0][0]

#     remaining = total_payable - total_paid

#     return {
#         "total_payable": total_payable,
#         "total_paid": total_paid,
#         "remaining": remaining
#     }


# @frappe.whitelist()
# def get_loan_repayment_details(loan_repayment):
#     """Get details of Loan Repayment for Payment Entry"""
#     doc = frappe.get_doc("Loan Repayment", loan_repayment)
#     loan = frappe.get_doc("Loan", doc.against_loan)

#     manual_payment_flag = doc.get('is_manual_payment')
#     is_manual = manual_payment_flag and int(manual_payment_flag) == 1

#     return {
#         "employee": loan.applicant,
#         "employee_name": frappe.db.get_value("Employee", loan.applicant, "employee_name"),
#         "loan": doc.against_loan,
#         "amount": doc.amount_paid,
#         "loan_account": loan.loan_account,
#         "posting_date": doc.posting_date,
#         "from_salary_slip": bool(doc.payroll_payable_account),
#         "is_manual": is_manual
#     }
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
            # Manual payment after resignation - NO GL Entry
            # Update loan status and schedule
            self.update_paid_amount_in_loan()
            self.set_status_in_loan()

            # ✅ NEW: Update Repayment Schedule
            self.update_repayment_schedule_on_manual_payment()

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
        ✅ Revert Repayment Schedule changes
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
            # Manual - just update loan status manually
            self.update_paid_amount_in_loan()
            self.set_status_in_loan()

            # ✅ NEW: Revert Repayment Schedule
            self.revert_repayment_schedule_on_cancel()

            # Update NPA status for all linked loan customers
            self.update_npa_status_on_cancel()

        # Unlink Payment Entry if exists
        if self.payment_entry:
            frappe.db.set_value("Loan Repayment", self.name,
                                "payment_entry", None)

    # def update_repayment_schedule_on_manual_payment(self):
    #     """
    #     ✅ Update Repayment Schedule when manual payment is made

    #     Logic:
    #     1. Get the loan's repayment schedule
    #     2. Mark pending installments as paid (starting from oldest)
    #     3. Update the schedule with payment details
    #     """
    #     if not self.against_loan:
    #         return

    #     try:
    #         loan = frappe.get_doc("Loan", self.against_loan)

    #         if not loan.repayment_schedule:
    #             frappe.log_error(
    #                 title=f"No Repayment Schedule for Loan {self.against_loan}",
    #                 message=f"Loan Repayment {self.name} - No schedule to update"
    #             )
    #             return

    #         amount_to_allocate = flt(self.amount_paid)

    #         # Get unpaid installments (sorted by payment date)
    #         for schedule in sorted(loan.repayment_schedule, key=lambda x: x.payment_date):
    #             if amount_to_allocate <= 0:
    #                 break

    #             # Check if installment is not yet paid
    #             # Use custom field if exists, or check if total_payment matches paid amount
    #             is_paid = False
    #             if hasattr(schedule, 'custom_is_paid'):
    #                 is_paid = schedule.custom_is_paid
    #             elif hasattr(schedule, 'custom_paid_amount'):
    #                 is_paid = flt(schedule.custom_paid_amount) >= flt(
    #                     schedule.total_payment)

    #             if not is_paid:
    #                 # Calculate how much of this installment we can pay
    #                 installment_total = flt(schedule.total_payment)
    #                 paid_amount = min(amount_to_allocate, installment_total)

    #                 # Update the schedule row
    #                 frappe.db.set_value(
    #                     "Repayment Schedule",
    #                     schedule.name,
    #                     {
    #                         "custom_paid_amount": paid_amount,
    #                         "custom_is_paid": 1 if paid_amount >= installment_total else 0,
    #                         "custom_payment_reference": self.name,
    #                         "custom_payment_date_actual": self.posting_date
    #                     }
    #                 )

    #                 amount_to_allocate -= paid_amount

    #                 frappe.logger().info(
    #                     f"Updated schedule {schedule.name}: paid {paid_amount} of {installment_total}"
    #                 )

    #         # If there's remaining amount after clearing all installments
    #         if amount_to_allocate > 0:
    #             frappe.msgprint(
    #                 _("Warning: Payment amount exceeds remaining installments by {0}").format(
    #                     frappe.format_value(amount_to_allocate, {
    #                                         "fieldtype": "Currency"})
    #                 ),
    #                 alert=True,
    #                 indicator="orange"
    #             )

    #         frappe.db.commit()

    #         frappe.msgprint(
    #             _("Repayment Schedule updated for manual payment"),
    #             alert=True,
    #             indicator="green"
    #         )

    #     except Exception as e:
    #         frappe.log_error(
    #             title=f"Error updating Repayment Schedule for {self.name}",
    #             message=frappe.get_traceback()
    #         )
    #         frappe.throw(
    #             _("Failed to update Repayment Schedule. Check Error Log."))

    def update_repayment_schedule_on_manual_payment(self):
        """
        ✅ Update Repayment Schedule when manual payment is made

        Logic:
        1. Get the loan's repayment schedule (linked records)
        2. Mark pending installments as paid (starting from oldest)
        3. Update the schedule with payment details
        """
        if not self.against_loan:
            return

        try:
            # ✅ Fetch all repayment schedules linked to this loan
            repayment_schedules = frappe.get_all(
                "Loan Repayment Schedule",
                filters={"loan": self.against_loan},
                fields=[
                    "name",
                    "payment_date",
                    "total_payment",
                    "custom_paid_amount",
                    "custom_is_paid"
                ],
                order_by="payment_date asc"
            )

            if not repayment_schedules:
                frappe.log_error(
                    title=f"No Repayment Schedule for Loan {self.against_loan}",
                    message=f"Loan Repayment {self.name} - No schedule to update"
                )
                return

            amount_to_allocate = flt(self.amount_paid)

            # ✅ Iterate through each schedule entry in chronological order
            for schedule in repayment_schedules:
                if amount_to_allocate <= 0:
                    break

                paid_amount_so_far = flt(schedule.custom_paid_amount)
                installment_total = flt(schedule.total_payment)
                remaining_installment_amount = installment_total - paid_amount_so_far

                if remaining_installment_amount <= 0:
                    continue  # already fully paid

                # Calculate how much to allocate to this installment
                paid_amount = min(amount_to_allocate,
                                  remaining_installment_amount)
                new_paid_amount = paid_amount_so_far + paid_amount

                frappe.db.set_value(
                    "Loan Repayment Schedule",
                    schedule.name,
                    {
                        "custom_paid_amount": new_paid_amount,
                        "custom_is_paid": 1 if new_paid_amount >= installment_total else 0,
                        "custom_payment_reference": self.name,
                        "custom_payment_date_actual": self.posting_date
                    }
                )

                frappe.logger().info(
                    f"Updated Loan Repayment Schedule {schedule.name}: "
                    f"paid {paid_amount} / {installment_total}"
                )

                amount_to_allocate -= paid_amount

            if amount_to_allocate > 0:
                frappe.msgprint(
                    _("Warning: Payment amount exceeds remaining installments by {0}").format(
                        frappe.format_value(amount_to_allocate, {
                                            "fieldtype": "Currency"})
                    ),
                    alert=True,
                    indicator="orange"
                )

            frappe.db.commit()
            frappe.msgprint(
                _("Repayment Schedule updated for manual payment"),
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

    # def revert_repayment_schedule_on_cancel(self):
    #     """
    #     ✅ Revert Repayment Schedule changes when cancelling manual payment
    #     """
    #     if not self.against_loan:
    #         return

    #     try:
    #         # Find all schedule rows that reference this repayment
    #         schedules = frappe.db.sql("""
    #             SELECT name, total_payment, custom_paid_amount
    #             FROM `tabRepayment Schedule`
    #             WHERE parent = %s
    #             AND custom_payment_reference = %s
    #         """, (self.against_loan, self.name), as_dict=1)

    #         for schedule in schedules:
    #             # Revert the payment
    #             new_paid_amount = flt(
    #                 schedule.custom_paid_amount) - flt(self.amount_paid)
    #             new_paid_amount = max(0, new_paid_amount)  # Don't go negative

    #             frappe.db.set_value(
    #                 "Repayment Schedule",
    #                 schedule.name,
    #                 {
    #                     "custom_paid_amount": new_paid_amount,
    #                     "custom_is_paid": 1 if new_paid_amount >= flt(schedule.total_payment) else 0,
    #                     "custom_payment_reference": None,
    #                     "custom_payment_date_actual": None
    #                 }
    #             )

    #         frappe.db.commit()

    #     except Exception as e:
    #         frappe.log_error(
    #             title=f"Error reverting Repayment Schedule for {self.name}",
    #             message=frappe.get_traceback()
    #         )
    def revert_repayment_schedule_on_cancel(self):
        """
        ✅ Revert Repayment Schedule changes when cancelling manual payment
        Works for connection-based (not child table) setup
        """
        if not self.against_loan:
            return

        try:
            # Find all schedule rows that reference this repayment
            schedules = frappe.get_all(
                "Loan Repayment Schedule",
                filters={
                    "loan": self.against_loan,
                    "custom_payment_reference": self.name
                },
                fields=["name", "total_payment", "custom_paid_amount"]
            )

            if not schedules:
                frappe.logger().info(
                    f"No linked repayment schedules found for {self.name} to revert."
                )
                return

            for schedule in schedules:
                # Revert the payment amount for this schedule
                new_paid_amount = flt(
                    schedule.custom_paid_amount) - flt(self.amount_paid)
                new_paid_amount = max(0, new_paid_amount)  # avoid negative

                frappe.db.set_value(
                    "Loan Repayment Schedule",
                    schedule.name,
                    {
                        "custom_paid_amount": new_paid_amount,
                        "custom_is_paid": 1 if new_paid_amount >= flt(schedule.total_payment) else 0,
                        "custom_payment_reference": None,
                        "custom_payment_date_actual": None
                    }
                )

                frappe.logger().info(
                    f"Reverted Loan Repayment Schedule {schedule.name}: "
                    f"paid amount set to {new_paid_amount}"
                )

            frappe.db.commit()

            frappe.msgprint(
                _("Repayment Schedule reverted for cancelled repayment {0}").format(
                    frappe.bold(self.name)
                ),
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
        Update NPA status when cancelling manual loan repayments
        This replicates the parent class behavior for NPA updates
        """
        try:
            from lending.loan_management.doctype.loan_repayment.loan_repayment import (
                update_all_linked_loan_customer_npa_status
            )

            update_all_linked_loan_customer_npa_status(
                loan=self.against_loan,
                posting_date=self.posting_date
            )
        except Exception as e:
            frappe.log_error(
                title=f"NPA Status Update Failed for {self.name}",
                message=str(e)
            )

    def make_gl_entries(self, cancel=0, adv_adj=0):
        """
        ✅ CRITICAL: Override to prevent GL Entry for manual payments
        """
        if self.check_is_manual_payment():
            frappe.logger().info(
                f"Skipping GL Entry for manual Loan Repayment {self.name}. "
                f"GL Entry will be created via Payment Entry."
            )
            return None

        return super(CustomLoanRepayment, self).make_gl_entries(cancel=cancel, adv_adj=adv_adj)

    def validate(self):
        """Add validation"""
        super(CustomLoanRepayment, self).validate()

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

    def check_is_manual_payment(self):
        """
        ✅ Check if this is a manual payment (after resignation)
        """
        manual_payment_flag = self.get('is_manual_payment')
        if manual_payment_flag and int(manual_payment_flag) == 1:
            return True

        if self.payroll_payable_account:
            return False

        salary_slip_loan = frappe.db.exists("Salary Slip Loan", {
            "loan_repayment_entry": self.name
        })
        if salary_slip_loan:
            return False

        return True

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


# ✅ NEW: Hook to prevent Salary Slip from deducting paid loans
def prevent_duplicate_loan_deduction(doc, method):
    """
    Hook for Salary Slip - before_save or validate
    Prevents deducting loans that are already fully paid manually
    """
    if not doc.loans:
        return

    loans_to_remove = []

    for idx, loan_row in enumerate(doc.loans):
        if not loan_row.loan:
            continue

        # Check if loan is fully paid
        loan = frappe.get_doc("Loan", loan_row.loan)

        # Calculate total paid
        total_paid = frappe.db.sql("""
            SELECT IFNULL(SUM(amount_paid), 0)
            FROM `tabLoan Repayment`
            WHERE against_loan = %s
            AND docstatus = 1
        """, loan_row.loan)[0][0]

        # Check if fully paid
        if flt(total_paid) >= flt(loan.total_payment):
            loans_to_remove.append(idx)
            frappe.msgprint(
                _("Loan {0} is already fully paid (Total: {1}). Removing from Salary Slip.").format(
                    frappe.bold(loan_row.loan),
                    frappe.format_value(total_paid, {"fieldtype": "Currency"})
                ),
                alert=True,
                indicator="orange"
            )

    # Remove fully paid loans (in reverse to avoid index issues)
    for idx in reversed(loans_to_remove):
        doc.loans.pop(idx)


@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
    """
    Create Payment Entry from Loan Repayment
    ✅ This creates the GL Entry for manual payments
    """

    def set_missing_values(source, target):
        loan_repayment = frappe.get_doc("Loan Repayment", source_name)

        if loan_repayment.docstatus != 1:
            frappe.throw(
                _("Loan Repayment must be submitted before creating Payment Entry"))

        if loan_repayment.payment_entry:
            frappe.throw(
                _("Payment Entry {0} already exists for this Loan Repayment").format(
                    frappe.bold(loan_repayment.payment_entry)
                )
            )

        manual_payment_flag = loan_repayment.get('is_manual_payment')
        is_manual = manual_payment_flag and int(manual_payment_flag) == 1

        if loan_repayment.payroll_payable_account and not is_manual:
            frappe.throw(
                _("Cannot create Payment Entry for Loan Repayment from Salary Slip. "
                  "GL Entry is already created via Salary Slip accounting.")
            )

        loan = frappe.get_doc("Loan", loan_repayment.against_loan)
        company = frappe.get_doc("Company", loan_repayment.company)

        target.payment_type = "Receive"
        target.party_type = "Employee"
        target.party = loan.applicant
        target.paid_amount = loan_repayment.amount_paid
        target.received_amount = loan_repayment.amount_paid
        target.reference_no = loan_repayment.name
        target.reference_date = loan_repayment.posting_date
        target.company = loan_repayment.company
        target.mode_of_payment = "Cash"

        target.paid_from = loan.loan_account

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

        target.append("references", {
            "reference_doctype": "Loan Repayment",
            "reference_name": loan_repayment.name,
            "total_amount": loan_repayment.amount_paid,
            "outstanding_amount": 0,
            "allocated_amount": 0
        })

        if hasattr(target, 'loan_repayment'):
            target.loan_repayment = loan_repayment.name

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

    manual_payment_flag = doc.get('is_manual_payment')
    is_manual = manual_payment_flag and int(manual_payment_flag) == 1

    return {
        "employee": loan.applicant,
        "employee_name": frappe.db.get_value("Employee", loan.applicant, "employee_name"),
        "loan": doc.against_loan,
        "amount": doc.amount_paid,
        "loan_account": loan.loan_account,
        "posting_date": doc.posting_date,
        "from_salary_slip": bool(doc.payroll_payable_account),
        "is_manual": is_manual
    }
