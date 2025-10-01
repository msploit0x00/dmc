import frappe
from frappe import _
from frappe.utils import flt
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry


class CustomPaymentEntry(PaymentEntry):
    """
    Custom Payment Entry Override
    Purpose: Update Loan Repayment after Payment Entry submission
    """

    def on_submit(self):
        """Override on_submit to add custom logic"""
        super(CustomPaymentEntry, self).on_submit()
        self.update_loan_repayment()

    def on_cancel(self):
        """Override on_cancel to handle loan repayment"""
        super(CustomPaymentEntry, self).on_cancel()
        self.cancel_loan_repayment()

    def update_loan_repayment(self):
        """Update Loan Repayment & Loan after Payment Entry submission"""

        loan_repayment_name = None

        # طريقة 1: من References
        for ref in self.references:
            if ref.reference_doctype == "Loan Repayment":
                loan_repayment_name = ref.reference_name
                break

        # طريقة 2: من Custom Field
        if not loan_repayment_name and hasattr(self, 'loan_repayment'):
            loan_repayment_name = self.loan_repayment

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

                # ✅ 3. لا نعمل GL Entry هنا - Payment Entry كافي!
                # القيد المحاسبي تم بواسطة Payment Entry:
                # Debit: الخزينة
                # Credit: حساب السلفة

                frappe.msgprint(
                    _("Loan Repayment {0} linked to Payment Entry").format(
                        frappe.bold(loan_repayment_name)
                    ),
                    alert=True,
                    indicator="green"
                )

                # 4. Update Loan status
                if loan_repayment.against_loan:
                    loan = frappe.get_doc("Loan", loan_repayment.against_loan)

                    # Calculate total paid (فقط من الدفعات المربوطة بـ Payment Entry)
                    total_paid = frappe.db.sql("""
                        SELECT IFNULL(SUM(amount_paid), 0)
                        FROM `tabLoan Repayment`
                        WHERE against_loan = %s
                        AND docstatus = 1
                        AND payment_entry IS NOT NULL
                    """, loan_repayment.against_loan)[0][0]

                    # If loan is fully paid
                    if flt(total_paid) >= flt(loan.loan_amount):
                        if loan.status not in ["Loan Closure Requested", "Closed"]:
                            loan.db_set('status', 'Loan Closure Requested')
                            frappe.msgprint(
                                _("Loan {0} marked as Loan Closure Requested").format(
                                    frappe.bold(loan.name)
                                ),
                                alert=True,
                                indicator="green"
                            )

                frappe.db.commit()

            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title=f"Error updating Loan Repayment {loan_repayment_name}"
                )
                frappe.throw(
                    _("Error while updating Loan Repayment. Please check Error Log.")
                )

    def cancel_loan_repayment(self):
        """Handle Loan Repayment when Payment Entry is cancelled"""

        loan_repayment_name = None

        # من References
        for ref in self.references:
            if ref.reference_doctype == "Loan Repayment":
                loan_repayment_name = ref.reference_name
                break

        # من Custom Field
        if not loan_repayment_name and hasattr(self, 'loan_repayment'):
            loan_repayment_name = self.loan_repayment

        if loan_repayment_name:
            try:
                # 1. Unlink Payment Entry from Loan Repayment
                frappe.db.set_value(
                    "Loan Repayment",
                    loan_repayment_name,
                    "payment_entry",
                    None
                )

                # 2. Get Loan Repayment
                loan_repayment = frappe.get_doc(
                    "Loan Repayment", loan_repayment_name)

                # ✅ 3. لا نعمل GL Entry Cancellation هنا
                # Payment Entry سيلغي القيد تلقائياً

                # 4. Update Loan Status
                if loan_repayment.against_loan:
                    loan = frappe.get_doc("Loan", loan_repayment.against_loan)

                    # Recalculate total paid
                    total_paid = frappe.db.sql("""
                        SELECT IFNULL(SUM(amount_paid), 0)
                        FROM `tabLoan Repayment`
                        WHERE against_loan = %s
                        AND docstatus = 1
                        AND payment_entry IS NOT NULL
                    """, loan_repayment.against_loan)[0][0]

                    # Update loan status
                    if flt(total_paid) < flt(loan.loan_amount):
                        if loan.status == "Loan Closure Requested":
                            loan.db_set('status', 'Disbursed')

                frappe.db.commit()

            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title=f"Error cancelling Loan Repayment {loan_repayment_name}"
                )
