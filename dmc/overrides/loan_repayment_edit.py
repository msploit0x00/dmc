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


# ==========================================
# ✅ Whitelisted Functions للـ Client Script
# ==========================================

@frappe.whitelist()
def get_remaining_loan_amount(loan_id):
    """
    ✅ حساب الباقي من القرض
    يستخدم في Client Script لعرض المعلومات
    """
    if not loan_id:
        frappe.throw(_("Loan ID is required"))

    # Get loan document
    loan = frappe.get_doc("Loan", loan_id)

    # Calculate total paid
    total_paid = frappe.db.sql("""
        SELECT IFNULL(SUM(amount_paid), 0)
        FROM `tabLoan Repayment`
        WHERE against_loan = %s 
        AND docstatus = 1
    """, loan_id)[0][0]

    # Calculate remaining
    total_payable = flt(loan.total_payment)
    remaining = flt(total_payable) - flt(total_paid)

    # ✅ Get currency from company
    company_currency = frappe.db.get_value(
        "Company", loan.company, "default_currency")

    return {
        "total_payable": total_payable,
        "total_paid": total_paid,
        "remaining": max(0, remaining),  # ✅ لا يمكن أن يكون سالب
        "currency": company_currency or frappe.defaults.get_global_default("currency")
    }


@frappe.whitelist()
def make_payment_entry(source_name):
    """
    ✅ إنشاء Payment Entry من Loan Repayment
    """
    loan_repayment = frappe.get_doc("Loan Repayment", source_name)

    # ✅ التحقق من أن Payment Entry غير موجود
    if loan_repayment.payment_entry:
        frappe.throw(_("Payment Entry {0} already exists for this Loan Repayment").format(
            frappe.bold(loan_repayment.payment_entry)
        ))

    # ✅ التحقق من أنه manual payment
    if not loan_repayment.check_is_manual_payment():
        frappe.throw(
            _("Payment Entry can only be created for manual loan repayments (not from Salary Slip)"))

    # Get loan document
    loan = frappe.get_doc("Loan", loan_repayment.against_loan)

    # ✅ Create Payment Entry manually
    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.posting_date = loan_repayment.posting_date or nowdate()
    pe.company = loan.company

    # Party details
    pe.party_type = loan.applicant_type
    pe.party = loan.applicant

    # Amount
    pe.paid_amount = flt(loan_repayment.amount_paid)
    pe.received_amount = flt(loan_repayment.amount_paid)

    # ✅ Accounts
    # Paid To (Debit) - Cash/Bank Account
    pe.paid_to = frappe.db.get_value(
        "Company", loan.company, "default_cash_account")
    if not pe.paid_to:
        frappe.throw(
            _("Please set Default Cash Account in Company {0}").format(loan.company))

    pe.paid_to_account_currency = frappe.db.get_value(
        "Account", pe.paid_to, "account_currency")

    # Paid From (Credit) - Loan Account
    pe.paid_from = loan.loan_account
    pe.paid_from_account_currency = frappe.db.get_value(
        "Account", loan.loan_account, "account_currency")

    # Reference
    pe.append("references", {
        "reference_doctype": "Loan Repayment",
        "reference_name": loan_repayment.name,
        "allocated_amount": flt(loan_repayment.amount_paid)
    })

    return pe.as_dict()


@frappe.whitelist()
def get_monthly_repayment_amount(loan_id):
    """
    ✅ حساب قيمة القسط الشهري من Loan Repayment Schedule
    """
    if not loan_id:
        return 0

    # Get latest active schedule
    active_schedule = frappe.get_all(
        "Loan Repayment Schedule",
        filters={
            "loan": loan_id,
            "status": "Active",
            "docstatus": 1
        },
        fields=["name"],
        order_by="posting_date desc",
        limit=1
    )

    if not active_schedule:
        return 0

    # Get first unpaid row
    schedule_doc = frappe.get_doc(
        "Loan Repayment Schedule", active_schedule[0].name)

    if not hasattr(schedule_doc, 'repayment_schedule') or not schedule_doc.repayment_schedule:
        return 0

    for row in schedule_doc.repayment_schedule:
        paid = flt(row.custom_paid_amount) if hasattr(
            row, 'custom_paid_amount') else 0
        total = flt(row.total_payment)

        if paid < total:
            # Return unpaid amount for this row
            return total - paid

    # All paid
    return 0


# ========================================
# 🔥 Salary Slip Functions
# ========================================

# def prevent_duplicate_loan_deduction(doc, method):
#     """
#     ✅ FINAL FIX: Only check ACTIVE schedules

#     Logic:
#     - Restructured schedules are OLD and should be IGNORED
#     - Only Active schedule matters
#     - If Active schedule has all installments paid → skip loan
#     """
#     if not doc.employee:
#         return

#     frappe.logger().info(
#         f"🔍 Checking loans for {doc.name} (Employee: {doc.employee}, Period: {doc.start_date} to {doc.end_date})"
#     )

#     # ✅ CRITICAL: Only check ACTIVE schedules (ignore Restructured!)
#     loans_with_unpaid = frappe.db.sql("""
#         SELECT DISTINCT
#             lrs.loan,
#             lrs.name as schedule_name,
#             l.loan_amount,
#             l.total_payment,
#             l.total_amount_paid,
#             COUNT(rs.name) as unpaid_count,
#             SUM(rs.total_payment - IFNULL(rs.custom_paid_amount, 0)) as unpaid_amount
#         FROM `tabLoan Repayment Schedule` lrs
#         INNER JOIN `tabLoan` l ON l.name = lrs.loan
#         INNER JOIN `tabRepayment Schedule` rs ON rs.parent = lrs.name
#         WHERE l.applicant = %s
#         AND l.company = %s
#         AND l.docstatus = 1
#         AND lrs.status = 'Active'  -- ✅ ONLY Active (ignore Restructured)
#         AND lrs.docstatus = 1
#         AND rs.parenttype = 'Loan Repayment Schedule'
#         AND rs.payment_date BETWEEN %s AND %s
#         AND (rs.custom_is_paid IS NULL OR rs.custom_is_paid = 0)
#         AND rs.total_payment > IFNULL(rs.custom_paid_amount, 0)
#         GROUP BY lrs.loan
#     """, (doc.employee, doc.company, doc.start_date, doc.end_date), as_dict=1)

#     if not loans_with_unpaid:
#         # ❌ NO unpaid installments in Active schedules
#         frappe.logger().info(
#             f"🚫 {doc.name}: No unpaid loan installments in period {doc.start_date} to {doc.end_date}"
#         )

#         # Clear everything
#         doc.set("loans", [])
#         doc.total_principal_amount = 0
#         doc.total_interest_amount = 0
#         doc.total_loan_repayment = 0
#         doc.calculate_net_pay()

#         # Set skip flag
#         doc.custom_skip_loan_repayment_creation = 1
#         doc.flags.skip_loan_repayment_entry = True

#         frappe.msgprint(
#             _("No unpaid loan installments in salary period {0} to {1}.<br>"
#               "All loans have been fully paid.").format(
#                 frappe.bold(doc.start_date),
#                 frappe.bold(doc.end_date)
#             ),
#             alert=True,
#             indicator="blue"
#         )
#         return

#     # ✅ STEP 2: Create dict of loans with unpaid amounts
#     loans_unpaid_dict = {loan.loan: loan for loan in loans_with_unpaid}

#     frappe.logger().info(
#         f"✅ {doc.name}: Found {len(loans_unpaid_dict)} loan(s) with unpaid installments"
#     )
#     for loan_name, loan_data in loans_unpaid_dict.items():
#         frappe.logger().info(
#             f"   - {loan_name} (Schedule: {loan_data.schedule_name}): "
#             f"{loan_data.unpaid_count} installment(s), Unpaid: {loan_data.unpaid_amount}"
#         )

#     # ✅ STEP 3: Validate Salary Slip loans table
#     if not doc.loans:
#         # No loans in table - skip
#         doc.custom_skip_loan_repayment_creation = 1
#         doc.flags.skip_loan_repayment_entry = True
#         frappe.logger().info(f"🚫 {doc.name}: loans table is empty")
#         return

#     valid_rows = []
#     removed_loans = []
#     adjusted_loans = []

#     for row in doc.loans:
#         if row.loan not in loans_unpaid_dict:
#             # This loan has NO unpaid installments in Active schedule
#             removed_loans.append(row.loan)
#             frappe.logger().info(
#                 f"❌ Removing {row.loan} - no unpaid installments in Active schedule"
#             )
#             continue

#         loan_data = loans_unpaid_dict[row.loan]
#         unpaid_in_period = flt(loan_data.unpaid_amount)

#         # ✅ Check if amount in row exceeds unpaid in Active schedule
#         if flt(row.total_payment) > unpaid_in_period + 0.01:  # tolerance
#             adjusted_loans.append({
#                 'loan': row.loan,
#                 'old_amount': flt(row.total_payment),
#                 'new_amount': unpaid_in_period,
#                 'schedule_name': loan_data.schedule_name
#             })

#             frappe.logger().info(
#                 f"⚙️ Adjusting {row.loan}: {row.total_payment} → {unpaid_in_period}"
#             )

#             # Adjust amounts
#             row.total_payment = unpaid_in_period
#             row.principal_amount = min(
#                 flt(row.principal_amount), unpaid_in_period)
#             row.interest_amount = unpaid_in_period - flt(row.principal_amount)

#         valid_rows.append(row)

#     # ✅ STEP 4: Update document
#     doc.set("loans", valid_rows)

#     if not valid_rows:
#         # All loans removed
#         doc.set("loans", [])
#         doc.total_principal_amount = 0
#         doc.total_interest_amount = 0
#         doc.total_loan_repayment = 0
#         doc.calculate_net_pay()

#         doc.custom_skip_loan_repayment_creation = 1
#         doc.flags.skip_loan_repayment_entry = True

#         frappe.logger().info(
#             f"🚫 {doc.name}: All loans removed - no unpaid installments in Active schedules"
#         )

#         frappe.msgprint(
#             _("All loans have been fully paid.<br>"
#               "Loan section hidden."),
#             alert=True,
#             indicator="blue"
#         )
#     else:
#         # Has valid unpaid loans
#         doc.custom_skip_loan_repayment_creation = 0
#         doc.flags.skip_loan_repayment_entry = False

#         # Recalculate totals
#         doc.total_principal_amount = sum(
#             [flt(l.principal_amount) for l in doc.loans])
#         doc.total_interest_amount = sum(
#             [flt(l.interest_amount) for l in doc.loans])
#         doc.total_loan_repayment = sum(
#             [flt(l.total_payment) for l in doc.loans])
#         doc.calculate_net_pay()

#         frappe.logger().info(
#             f"✅ {doc.name}: Keeping {len(valid_rows)} loan(s) with unpaid installments"
#         )

#         # Show user feedback
#         if removed_loans or adjusted_loans:
#             messages = []
#             if removed_loans:
#                 messages.append(
#                     _("Removed loan(s): {0} (fully paid or no dues in this period)").format(
#                         ", ".join([frappe.bold(l) for l in removed_loans])
#                     )
#                 )
#             if adjusted_loans:
#                 for adj in adjusted_loans:
#                     messages.append(
#                         _("Loan {0}: Amount adjusted from {1} to {2}<br>"
#                           "<small>Based on Active schedule: {3}</small>").format(
#                             frappe.bold(adj['loan']),
#                             frappe.format_value(adj['old_amount'], {
#                                                 "fieldtype": "Currency"}),
#                             frappe.bold(frappe.format_value(
#                                 adj['new_amount'], {"fieldtype": "Currency"})),
#                             adj['schedule_name']
#                         )
#                     )

#             if messages:
#                 frappe.msgprint(
#                     "<br><br>".join(messages),
#                     title=_("Loan Deductions Updated"),
#                     indicator="orange"
#                 )

def prevent_duplicate_loan_deduction(doc, method):
    """
    ✅ ULTIMATE FIX: Only check ACTIVE schedules + ignore manual payments

    Logic:
    - Restructured schedules are OLD and should be IGNORED
    - Only Active schedule matters
    - If Active schedule has all installments paid → skip loan
    - ✅ NEW: Check if loan was paid manually (via Payment Entry) → skip it!
    """
    if not doc.employee:
        return

    frappe.logger().info(
        f"🔍 Checking loans for {doc.name} (Employee: {doc.employee}, Period: {doc.start_date} to {doc.end_date})"
    )

    # ✅ STEP 1: Get loans with MANUAL payment (via Payment Entry)
    loans_with_manual_payment = frappe.db.sql("""
        SELECT DISTINCT l.name as loan
        FROM `tabLoan` l
        INNER JOIN `tabLoan Repayment` lr ON lr.against_loan = l.name
        INNER JOIN `tabPayment Entry` pe ON pe.name = lr.payment_entry
        WHERE l.applicant = %s
        AND l.company = %s
        AND l.docstatus = 1
        AND lr.docstatus = 1
        AND pe.docstatus = 1
        AND pe.custom_is_manual_loan_payment = 1
    """, (doc.employee, doc.company), as_dict=1)

    manual_loan_set = {loan.loan for loan in loans_with_manual_payment}

    if manual_loan_set:
        frappe.logger().info(
            f"🚫 Found {len(manual_loan_set)} loan(s) with MANUAL payment: {', '.join(manual_loan_set)}"
        )

    # ✅ STEP 2: CRITICAL: Only check ACTIVE schedules (ignore Restructured!)
    loans_with_unpaid = frappe.db.sql("""
        SELECT DISTINCT 
            lrs.loan,
            lrs.name as schedule_name,
            l.loan_amount,
            l.total_payment,
            l.total_amount_paid,
            COUNT(rs.name) as unpaid_count,
            SUM(rs.total_payment - IFNULL(rs.custom_paid_amount, 0)) as unpaid_amount
        FROM `tabLoan Repayment Schedule` lrs
        INNER JOIN `tabLoan` l ON l.name = lrs.loan
        INNER JOIN `tabRepayment Schedule` rs ON rs.parent = lrs.name
        WHERE l.applicant = %s
        AND l.company = %s
        AND l.docstatus = 1
        AND lrs.status = 'Active'
        AND lrs.docstatus = 1
        AND rs.parenttype = 'Loan Repayment Schedule'
        AND rs.payment_date BETWEEN %s AND %s
        AND (rs.custom_is_paid IS NULL OR rs.custom_is_paid = 0)
        AND rs.total_payment > IFNULL(rs.custom_paid_amount, 0)
        GROUP BY lrs.loan
    """, (doc.employee, doc.company, doc.start_date, doc.end_date), as_dict=1)

    # ✅ STEP 3: Filter out loans with manual payment
    loans_with_unpaid = [
        loan for loan in loans_with_unpaid
        if loan.loan not in manual_loan_set
    ]

    if not loans_with_unpaid:
        # ❌ NO unpaid installments in Active schedules OR all paid manually
        reason = "paid manually" if manual_loan_set else "no unpaid installments"
        frappe.logger().info(
            f"🚫 {doc.name}: No loans to deduct ({reason})"
        )

        # Clear everything
        doc.set("loans", [])
        doc.total_principal_amount = 0
        doc.total_interest_amount = 0
        doc.total_loan_repayment = 0
        doc.calculate_net_pay()

        # Set skip flag
        doc.custom_skip_loan_repayment_creation = 1
        doc.flags.skip_loan_repayment_entry = True

        if manual_loan_set:
            frappe.msgprint(
                _("القروض التالية تم دفعها يدوياً (عن طريق Payment Entry) ولن يتم خصمها:<br>{0}").format(
                    "<br>".join([f"- {loan}" for loan in manual_loan_set])
                ),
                alert=True,
                indicator="blue"
            )
        else:
            frappe.msgprint(
                _("No unpaid loan installments in salary period {0} to {1}.<br>"
                  "All loans have been fully paid.").format(
                    frappe.bold(doc.start_date),
                    frappe.bold(doc.end_date)
                ),
                alert=True,
                indicator="blue"
            )
        return

    # ✅ STEP 4: Create dict of loans with unpaid amounts
    loans_unpaid_dict = {loan.loan: loan for loan in loans_with_unpaid}

    frappe.logger().info(
        f"✅ {doc.name}: Found {len(loans_unpaid_dict)} loan(s) with unpaid installments"
    )
    for loan_name, loan_data in loans_unpaid_dict.items():
        frappe.logger().info(
            f"   - {loan_name} (Schedule: {loan_data.schedule_name}): "
            f"{loan_data.unpaid_count} installment(s), Unpaid: {loan_data.unpaid_amount}"
        )

    # ✅ STEP 5: Validate Salary Slip loans table
    if not doc.loans:
        doc.custom_skip_loan_repayment_creation = 1
        doc.flags.skip_loan_repayment_entry = True
        frappe.logger().info(f"🚫 {doc.name}: loans table is empty")
        return

    valid_rows = []
    removed_loans = []
    adjusted_loans = []
    manually_paid_loans = []

    for row in doc.loans:
        # ✅ Check if paid manually
        if row.loan in manual_loan_set:
            manually_paid_loans.append(row.loan)
            frappe.logger().info(
                f"❌ Removing {row.loan} - PAID MANUALLY via Payment Entry"
            )
            continue

        if row.loan not in loans_unpaid_dict:
            removed_loans.append(row.loan)
            frappe.logger().info(
                f"❌ Removing {row.loan} - no unpaid installments in Active schedule"
            )
            continue

        loan_data = loans_unpaid_dict[row.loan]
        unpaid_in_period = flt(loan_data.unpaid_amount)

        if flt(row.total_payment) > unpaid_in_period + 0.01:
            adjusted_loans.append({
                'loan': row.loan,
                'old_amount': flt(row.total_payment),
                'new_amount': unpaid_in_period,
                'schedule_name': loan_data.schedule_name
            })

            frappe.logger().info(
                f"⚙️ Adjusting {row.loan}: {row.total_payment} → {unpaid_in_period}"
            )

            row.total_payment = unpaid_in_period
            row.principal_amount = min(
                flt(row.principal_amount), unpaid_in_period)
            row.interest_amount = unpaid_in_period - flt(row.principal_amount)

        valid_rows.append(row)

    # ✅ STEP 6: Update document
    doc.set("loans", valid_rows)

    if not valid_rows:
        doc.set("loans", [])
        doc.total_principal_amount = 0
        doc.total_interest_amount = 0
        doc.total_loan_repayment = 0
        doc.calculate_net_pay()

        doc.custom_skip_loan_repayment_creation = 1
        doc.flags.skip_loan_repayment_entry = True

        frappe.logger().info(
            f"🚫 {doc.name}: All loans removed"
        )

        if manually_paid_loans:
            frappe.msgprint(
                _("القروض التالية تم دفعها يدوياً ولن يتم خصمها:<br>{0}").format(
                    "<br>".join(
                        [f"- {frappe.bold(loan)}" for loan in manually_paid_loans])
                ),
                alert=True,
                indicator="blue"
            )
        else:
            frappe.msgprint(
                _("All loans have been fully paid.<br>Loan section hidden."),
                alert=True,
                indicator="blue"
            )
    else:
        doc.custom_skip_loan_repayment_creation = 0
        doc.flags.skip_loan_repayment_entry = False

        doc.total_principal_amount = sum(
            [flt(l.principal_amount) for l in doc.loans])
        doc.total_interest_amount = sum(
            [flt(l.interest_amount) for l in doc.loans])
        doc.total_loan_repayment = sum(
            [flt(l.total_payment) for l in doc.loans])
        doc.calculate_net_pay()

        frappe.logger().info(
            f"✅ {doc.name}: Keeping {len(valid_rows)} loan(s) with unpaid installments"
        )

        # Show user feedback
        if removed_loans or adjusted_loans or manually_paid_loans:
            messages = []

            if manually_paid_loans:
                messages.append(
                    _("✅ القروض المدفوعة يدوياً (تم تجاهلها):<br>{0}").format(
                        "<br>".join(
                            [f"  - {frappe.bold(loan)}" for loan in manually_paid_loans])
                    )
                )

            if removed_loans:
                messages.append(
                    _("Removed loan(s): {0} (fully paid or no dues in this period)").format(
                        ", ".join([frappe.bold(l) for l in removed_loans])
                    )
                )

            if adjusted_loans:
                for adj in adjusted_loans:
                    messages.append(
                        _("Loan {0}: Amount adjusted from {1} to {2}<br>"
                          "<small>Based on Active schedule: {3}</small>").format(
                            frappe.bold(adj['loan']),
                            frappe.format_value(adj['old_amount'], {
                                                "fieldtype": "Currency"}),
                            frappe.bold(frappe.format_value(
                                adj['new_amount'], {"fieldtype": "Currency"})),
                            adj['schedule_name']
                        )
                    )

            if messages:
                frappe.msgprint(
                    "<br><br>".join(messages),
                    title=_("Loan Deductions Updated"),
                    indicator="orange" if not manually_paid_loans else "blue"
                )


def persist_skip_flag_on_submit(doc, method):
    """
    ✅ CRITICAL: Persist skip flag in database after submit
    """
    if doc.get("custom_skip_loan_repayment_creation") == 1:
        frappe.logger().info(
            f"💾 Persisting skip flag for {doc.name} in database"
        )

        # Save to database
        frappe.db.set_value(
            "Salary Slip",
            doc.name,
            "custom_skip_loan_repayment_creation",
            1,
            update_modified=False
        )

        frappe.db.commit()


# def custom_make_loan_repayment_entry(doc):
#     """
#     ✅ ULTIMATE FIX: Re-check schedule before creating repayment
#     """

#     # CHECK 0: Re-clean loans table
#     prevent_duplicate_loan_deduction(
#         doc, method="before_loan_repayment_creation")

#     # CHECK 1: Skip flag
#     skip_flag = frappe.db.get_value(
#         "Salary Slip", doc.name, "custom_skip_loan_repayment_creation")
#     if flt(skip_flag) == 1:
#         frappe.logger().info(f"🚫 SKIP: {doc.name} - skip flag set")
#         return None

#     # CHECK 2: Empty loans table
#     if not doc.get("loans") or len(doc.loans) == 0:
#         frappe.logger().info(f"🚫 SKIP: {doc.name} - loans table empty")
#         return None

#     # ✅ CHECK 3: Verify each loan has UNPAID installments in ACTIVE schedule
#     for loan_row in doc.loans:
#         active_schedule = frappe.db.sql("""
#             SELECT name
#             FROM `tabLoan Repayment Schedule`
#             WHERE loan = %s
#             AND status = 'Active'
#             AND docstatus = 1
#             ORDER BY posting_date DESC
#             LIMIT 1
#         """, loan_row.loan, as_dict=1)

#         if not active_schedule:
#             continue

#         # ✅ Check if ALL installments in this period are PAID
#         unpaid_count = frappe.db.sql("""
#             SELECT COUNT(*) as count
#             FROM `tabRepayment Schedule` rs
#             WHERE rs.parent = %s
#             AND rs.parenttype = 'Loan Repayment Schedule'
#             AND rs.payment_date BETWEEN %s AND %s
#             AND (rs.custom_is_paid IS NULL OR rs.custom_is_paid = 0)
#             AND rs.total_payment > IFNULL(rs.custom_paid_amount, 0)
#         """, (active_schedule[0].name, doc.start_date, doc.end_date))[0][0] or 0

#         if unpaid_count == 0:
#             frappe.logger().warning(
#                 f"⚠️ PREVENTED: Loan {loan_row.loan} has NO unpaid installments "
#                 f"in period {doc.start_date} to {doc.end_date} "
#                 f"(all marked as paid, possibly by Payment Entry)"
#             )

#             # Remove from loans table
#             doc.loans.remove(loan_row)

#     # CHECK 4: After removal, check if loans table is empty
#     if not doc.loans or len(doc.loans) == 0:
#         frappe.logger().warning(
#             f"🚫 PREVENTED: All loans in {doc.name} are fully paid - "
#             f"Loan Repayment Entry creation cancelled"
#         )

#         # Clean up
#         doc.set("loans", [])
#         doc.total_loan_repayment = 0
#         doc.custom_skip_loan_repayment_creation = 1

#         frappe.db.set_value(
#             "Salary Slip",
#             doc.name,
#             {
#                 "custom_skip_loan_repayment_creation": 1,
#                 "total_loan_repayment": 0
#             },
#             update_modified=False
#         )
#         frappe.db.commit()

#         return None

#     # ✅ All checks passed - create repayment
#     from erpnext.payroll.doctype.salary_slip.salary_slip import make_loan_repayment_entry
#     return make_loan_repayment_entry(doc)
4


def custom_make_loan_repayment_entry(doc):
    """
    ✅ ULTIMATE FIX: Re-check schedule + manual payments before creating repayment
    """

    # CHECK 0: Re-clean loans table
    prevent_duplicate_loan_deduction(
        doc, method="before_loan_repayment_creation")

    # CHECK 1: Skip flag
    skip_flag = frappe.db.get_value(
        "Salary Slip", doc.name, "custom_skip_loan_repayment_creation")
    if flt(skip_flag) == 1:
        frappe.logger().info(f"🚫 SKIP: {doc.name} - skip flag set")
        return None

    # CHECK 2: Empty loans table
    if not doc.get("loans") or len(doc.loans) == 0:
        frappe.logger().info(f"🚫 SKIP: {doc.name} - loans table empty")
        return None

    # ✅ CHECK 3: Verify each loan is NOT paid manually
    for loan_row in doc.loans:
        # Check if this loan has manual payment via Payment Entry
        has_manual_payment = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabLoan Repayment` lr
            INNER JOIN `tabPayment Entry` pe ON pe.name = lr.payment_entry
            WHERE lr.against_loan = %s
            AND lr.docstatus = 1
            AND pe.docstatus = 1
            AND pe.custom_is_manual_loan_payment = 1
        """, loan_row.loan)[0][0] or 0

        if has_manual_payment > 0:
            frappe.logger().warning(
                f"⚠️ PREVENTED: Loan {loan_row.loan} was paid MANUALLY via Payment Entry"
            )
            doc.loans.remove(loan_row)
            continue

        # Check Active schedule
        active_schedule = frappe.db.sql("""
            SELECT name
            FROM `tabLoan Repayment Schedule`
            WHERE loan = %s
            AND status = 'Active'
            AND docstatus = 1
            ORDER BY posting_date DESC
            LIMIT 1
        """, loan_row.loan, as_dict=1)

        if not active_schedule:
            doc.loans.remove(loan_row)
            continue

        # ✅ Check if ALL installments in this period are PAID
        unpaid_count = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabRepayment Schedule` rs
            WHERE rs.parent = %s
            AND rs.parenttype = 'Loan Repayment Schedule'
            AND rs.payment_date BETWEEN %s AND %s
            AND (rs.custom_is_paid IS NULL OR rs.custom_is_paid = 0)
            AND rs.total_payment > IFNULL(rs.custom_paid_amount, 0)
        """, (active_schedule[0].name, doc.start_date, doc.end_date))[0][0] or 0

        if unpaid_count == 0:
            frappe.logger().warning(
                f"⚠️ PREVENTED: Loan {loan_row.loan} has NO unpaid installments "
                f"in period {doc.start_date} to {doc.end_date}"
            )
            doc.loans.remove(loan_row)

    # CHECK 4: After removal, check if loans table is empty
    if not doc.loans or len(doc.loans) == 0:
        frappe.logger().warning(
            f"🚫 PREVENTED: All loans in {doc.name} are either paid manually or fully paid - "
            f"Loan Repayment Entry creation cancelled"
        )

        # Clean up
        doc.set("loans", [])
        doc.total_loan_repayment = 0
        doc.custom_skip_loan_repayment_creation = 1

        frappe.db.set_value(
            "Salary Slip",
            doc.name,
            {
                "custom_skip_loan_repayment_creation": 1,
                "total_loan_repayment": 0
            },
            update_modified=False
        )
        frappe.db.commit()

        return None

    # ✅ All checks passed - create repayment
    frappe.logger().info(
        f"✅ Creating Loan Repayment Entry for {doc.name} with {len(doc.loans)} loan(s)"
    )

    from erpnext.payroll.doctype.salary_slip.salary_slip import make_loan_repayment_entry
    return make_loan_repayment_entry(doc)
