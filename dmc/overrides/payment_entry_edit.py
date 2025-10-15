import frappe
from frappe import _
from frappe.utils import flt
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

                # 3. Update Loan status if needed
                if loan_repayment.against_loan:
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

                # 2. Unlink Payment Entry from Loan Repayment
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

                # 3. Update Loan Status if needed
                if against_loan:
                    self.update_loan_closure_status(against_loan)

                frappe.db.commit()

            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title=f"Error unlinking Loan Repayment {loan_repayment_name}"
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
            if flt(total_paid) >= flt(loan.loan_amount):
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
                                flt(loan.loan_amount) - flt(total_paid),
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
