# import frappe
# from frappe import _
# from frappe.utils import flt
# from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry


# class CustomPaymentEntry(PaymentEntry):
#     """
#     Custom Payment Entry Override
#     Purpose: Link Payment Entry to Loan Repayment after submission
#     """

#     def on_submit(self):
#         """Override on_submit to add custom logic"""
#         # Call parent first - this creates GL Entry
#         super(CustomPaymentEntry, self).on_submit()

#         # Then link to Loan Repayment
#         self.update_loan_repayment()

#     def on_cancel(self):
#         """Override on_cancel to handle loan repayment"""
#         # Unlink Loan Repayment first
#         self.cancel_loan_repayment()

#         # Then call parent - this cancels GL Entry
#         super(CustomPaymentEntry, self).on_cancel()

#     def update_loan_repayment(self):
#         """
#         Link Payment Entry to Loan Repayment after submission
#         ✅ Only updates the link - GL Entry already created by Payment Entry
#         """
#         loan_repayment_name = self.get_loan_repayment_name()

#         if loan_repayment_name:
#             try:
#                 # 1. Link Payment Entry to Loan Repayment
#                 frappe.db.set_value(
#                     "Loan Repayment",
#                     loan_repayment_name,
#                     "payment_entry",
#                     self.name
#                 )

#                 # 2. Get Loan Repayment
#                 loan_repayment = frappe.get_doc(
#                     "Loan Repayment", loan_repayment_name)

#                 frappe.msgprint(
#                     _("Payment Entry {0} linked to Loan Repayment {1}").format(
#                         frappe.bold(self.name),
#                         frappe.bold(loan_repayment_name)
#                     ),
#                     alert=True,
#                     indicator="green"
#                 )

#                 # 3. Update Loan status if needed
#                 if loan_repayment.against_loan:
#                     self.update_loan_closure_status(
#                         loan_repayment.against_loan)

#                 frappe.db.commit()

#             except Exception as e:
#                 frappe.log_error(
#                     message=frappe.get_traceback(),
#                     title=f"Error linking Payment Entry to Loan Repayment {loan_repayment_name}"
#                 )
#                 frappe.throw(
#                     _("Error while linking to Loan Repayment. Check Error Log for details.")
#                 )

#     def cancel_loan_repayment(self):
#         """
#         Unlink Payment Entry from Loan Repayment when cancelled
#         """
#         loan_repayment_name = self.get_loan_repayment_name()

#         if loan_repayment_name:
#             try:
#                 # 1. Get loan before unlinking
#                 loan_repayment = frappe.get_doc(
#                     "Loan Repayment", loan_repayment_name)
#                 against_loan = loan_repayment.against_loan

#                 # 2. Unlink Payment Entry from Loan Repayment
#                 frappe.db.set_value(
#                     "Loan Repayment",
#                     loan_repayment_name,
#                     "payment_entry",
#                     None
#                 )

#                 frappe.msgprint(
#                     _("Payment Entry unlinked from Loan Repayment {0}").format(
#                         frappe.bold(loan_repayment_name)
#                     ),
#                     alert=True,
#                     indicator="orange"
#                 )

#                 # 3. Update Loan Status if needed
#                 if against_loan:
#                     self.update_loan_closure_status(against_loan)

#                 frappe.db.commit()

#             except Exception as e:
#                 frappe.log_error(
#                     message=frappe.get_traceback(),
#                     title=f"Error unlinking Loan Repayment {loan_repayment_name}"
#                 )

#     def get_loan_repayment_name(self):
#         """
#         Get Loan Repayment name from references or custom field
#         """
#         # Method 1: From References table
#         for ref in self.references:
#             if ref.reference_doctype == "Loan Repayment":
#                 return ref.reference_name

#         # Method 2: From Custom Field (if exists)
#         if hasattr(self, 'loan_repayment') and self.loan_repayment:
#             return self.loan_repayment

#         return None

#     def update_loan_closure_status(self, loan_name):
#         """
#         Update Loan closure status based on total payments
#         """
#         try:
#             loan = frappe.get_doc("Loan", loan_name)

#             # Calculate total paid from all SUBMITTED Loan Repayments
#             total_paid = frappe.db.sql("""
#                 SELECT IFNULL(SUM(amount_paid), 0)
#                 FROM `tabLoan Repayment`
#                 WHERE against_loan = %s
#                 AND docstatus = 1
#             """, loan_name)[0][0]

#             # Check if loan is fully paid
#             if flt(total_paid) >= flt(loan.loan_amount):
#                 if loan.status not in ["Loan Closure Requested", "Closed"]:
#                     loan.db_set('status', 'Loan Closure Requested')
#                     frappe.msgprint(
#                         _("Loan {0} marked as 'Loan Closure Requested' (Total Paid: {1})").format(
#                             frappe.bold(loan.name),
#                             frappe.bold(frappe.format_value(
#                                 total_paid, {"fieldtype": "Currency"}))
#                         ),
#                         alert=True,
#                         indicator="green"
#                     )
#             else:
#                 # If previously marked as closure requested but now insufficient payment
#                 if loan.status == "Loan Closure Requested":
#                     loan.db_set('status', 'Disbursed')
#                     frappe.msgprint(
#                         _("Loan {0} status changed to 'Disbursed' (Remaining: {1})").format(
#                             frappe.bold(loan.name),
#                             frappe.bold(frappe.format_value(
#                                 flt(loan.loan_amount) - flt(total_paid),
#                                 {"fieldtype": "Currency"}
#                             ))
#                         ),
#                         alert=True,
#                         indicator="orange"
#                     )

#         except Exception as e:
#             frappe.log_error(
#                 message=frappe.get_traceback(),
#                 title=f"Error updating Loan closure status for {loan_name}"
#             )
import frappe
from frappe import _
from frappe.utils import flt, getdate
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry


class CustomPaymentEntry(PaymentEntry):
    """
    Custom Payment Entry Override
    Purpose: Link Payment Entry to Loan Repayment after submission
    """

    def on_submit(self):
        """Override on_submit to add custom logic"""
        # Call parent first - this creates GL Entry
        super(CustomPaymentEntry, self).on_submit()

        # Then link to Loan Repayment
        self.update_loan_repayment()

    def on_cancel(self):
        """Override on_cancel to handle loan repayment"""
        # Unlink Loan Repayment first
        self.cancel_loan_repayment()

        # Then call parent - this cancels GL Entry
        super(CustomPaymentEntry, self).on_cancel()

    def update_loan_repayment(self):
        """
        Link Payment Entry to Loan Repayment after submission
        ✅ Only updates the link - GL Entry already created by Payment Entry
        """
        loan_repayment_name = self.get_loan_repayment_name()

        if loan_repayment_name:
            try:
                # 1. Link Payment Entry to Loan Repayment
                frappe.db.set_value(
                    "Loan Repayment",
                    loan_repayment_name,
                    "payment_entry",
                    self.name
                )

                # 2. Get Loan Repayment
                loan_repayment = frappe.get_doc(
                    "Loan Repayment", loan_repayment_name)

                frappe.msgprint(
                    _("Payment Entry {0} linked to Loan Repayment {1}").format(
                        frappe.bold(self.name),
                        frappe.bold(loan_repayment_name)
                    ),
                    alert=True,
                    indicator="green"
                )

                # 3. ✅ NEW: Update Repayment Schedule
                if loan_repayment.against_loan:
                    self.mark_loan_schedule_as_paid(
                        loan_repayment.against_loan,
                        loan_repayment.amount_paid,
                        loan_repayment.posting_date
                    )

                    # Update Loan status
                    self.update_loan_closure_status(
                        loan_repayment.against_loan)

                frappe.db.commit()

            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title=f"Error linking Payment Entry to Loan Repayment {loan_repayment_name}"
                )
                frappe.throw(
                    _("Error while linking to Loan Repayment. Check Error Log for details.")
                )

    def cancel_loan_repayment(self):
        """
        Unlink Payment Entry from Loan Repayment when cancelled
        """
        loan_repayment_name = self.get_loan_repayment_name()

        if loan_repayment_name:
            try:
                # 1. Get loan before unlinking
                loan_repayment = frappe.get_doc(
                    "Loan Repayment", loan_repayment_name)
                against_loan = loan_repayment.against_loan

                # 2. ✅ NEW: Revert Schedule changes
                if against_loan:
                    self.unmark_loan_schedule(
                        against_loan,
                        loan_repayment.amount_paid,
                        loan_repayment.posting_date
                    )

                # 3. Unlink Payment Entry from Loan Repayment
                frappe.db.set_value(
                    "Loan Repayment",
                    loan_repayment_name,
                    "payment_entry",
                    None
                )

                frappe.msgprint(
                    _("Payment Entry unlinked from Loan Repayment {0}").format(
                        frappe.bold(loan_repayment_name)
                    ),
                    alert=True,
                    indicator="orange"
                )

                # 4. Update Loan Status if needed
                if against_loan:
                    self.update_loan_closure_status(against_loan)

                frappe.db.commit()

            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title=f"Error unlinking Loan Repayment {loan_repayment_name}"
                )

    def mark_loan_schedule_as_paid(self, loan_name, amount_paid, posting_date):
        """
        ✅ Mark Repayment Schedule entries as paid (oldest first)
        This prevents Salary Slip from trying to deduct already-paid installments
        """
        try:
            loan = frappe.get_doc("Loan", loan_name)
            remaining_amount = flt(amount_paid)
            posting_date = getdate(posting_date)

            # Get unpaid schedule entries (oldest first)
            unpaid_schedules = [row for row in loan.repayment_schedule
                                if not row.is_paid and flt(row.total_payment) > flt(row.paid_amount)]

            # Sort by payment date
            unpaid_schedules.sort(key=lambda x: getdate(x.payment_date))

            for schedule in unpaid_schedules:
                if remaining_amount <= 0:
                    break

                outstanding = flt(schedule.total_payment) - \
                    flt(schedule.paid_amount)

                if outstanding <= 0:
                    continue

                # Calculate how much to pay for this schedule
                payment_for_schedule = min(remaining_amount, outstanding)

                # Update schedule row
                new_paid_amount = flt(
                    schedule.paid_amount) + payment_for_schedule
                schedule.paid_amount = new_paid_amount

                # Mark as paid if fully paid
                if flt(new_paid_amount) >= flt(schedule.total_payment):
                    schedule.is_paid = 1

                remaining_amount -= payment_for_schedule

                frappe.logger().info(
                    f"Marked schedule {schedule.payment_date} as paid "
                    f"(Paid: {new_paid_amount}/{schedule.total_payment})"
                )

            # Save loan without triggering validations
            loan.flags.ignore_validate = True
            loan.save(ignore_permissions=True)

            frappe.msgprint(
                _("Loan Repayment Schedule updated successfully for Loan {0}").format(
                    frappe.bold(loan.name)
                ),
                alert=True,
                indicator="green"
            )

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"Error updating Loan Schedule for {loan_name}"
            )

    def unmark_loan_schedule(self, loan_name, amount_paid, posting_date):
        """
        ✅ Revert Schedule changes when Payment Entry is cancelled
        """
        try:
            loan = frappe.get_doc("Loan", loan_name)
            remaining_amount = flt(amount_paid)
            posting_date = getdate(posting_date)

            # Get paid schedule entries (newest first for reversal)
            paid_schedules = [row for row in loan.repayment_schedule
                              if row.is_paid or flt(row.paid_amount) > 0]

            # Sort by payment date (reverse)
            paid_schedules.sort(key=lambda x: getdate(
                x.payment_date), reverse=True)

            for schedule in paid_schedules:
                if remaining_amount <= 0:
                    break

                # Calculate how much to deduct
                deduction = min(remaining_amount, flt(schedule.paid_amount))

                # Update schedule row
                schedule.paid_amount = flt(schedule.paid_amount) - deduction

                # Unmark if no longer fully paid
                if flt(schedule.paid_amount) < flt(schedule.total_payment):
                    schedule.is_paid = 0

                remaining_amount -= deduction

            # Save loan
            loan.flags.ignore_validate = True
            loan.save(ignore_permissions=True)

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"Error reverting Loan Schedule for {loan_name}"
            )

    def get_loan_repayment_name(self):
        """
        Get Loan Repayment name from references or custom field
        """
        # Method 1: From References table
        for ref in self.references:
            if ref.reference_doctype == "Loan Repayment":
                return ref.reference_name

        # Method 2: From Custom Field (if exists)
        if hasattr(self, 'loan_repayment') and self.loan_repayment:
            return self.loan_repayment

        return None

    def update_loan_closure_status(self, loan_name):
        """
        Update Loan closure status based on total payments
        """
        try:
            loan = frappe.get_doc("Loan", loan_name)

            # Calculate total paid from all SUBMITTED Loan Repayments
            total_paid = frappe.db.sql("""
                SELECT IFNULL(SUM(amount_paid), 0)
                FROM `tabLoan Repayment`
                WHERE against_loan = %s
                AND docstatus = 1
            """, loan_name)[0][0]

            # Check if loan is fully paid
            if flt(total_paid) >= flt(loan.total_payment):
                if loan.status not in ["Loan Closure Requested", "Closed"]:
                    loan.db_set('status', 'Loan Closure Requested')
                    frappe.msgprint(
                        _("Loan {0} marked as 'Loan Closure Requested' (Total Paid: {1})").format(
                            frappe.bold(loan.name),
                            frappe.bold(frappe.format_value(
                                total_paid, {"fieldtype": "Currency"}))
                        ),
                        alert=True,
                        indicator="green"
                    )
            else:
                # If previously marked as closure requested but now insufficient payment
                if loan.status == "Loan Closure Requested":
                    loan.db_set('status', 'Disbursed')
                    frappe.msgprint(
                        _("Loan {0} status changed to 'Disbursed' (Remaining: {1})").format(
                            frappe.bold(loan.name),
                            frappe.bold(frappe.format_value(
                                flt(loan.total_payment) - flt(total_paid),
                                {"fieldtype": "Currency"}
                            ))
                        ),
                        alert=True,
                        indicator="orange"
                    )

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"Error updating Loan closure status for {loan_name}"
            )
