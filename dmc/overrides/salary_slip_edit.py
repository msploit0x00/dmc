# ========================================
# الملف: dmc/overrides/salary_slip_edit.py
# ========================================

import frappe
from frappe import _
from frappe.utils import flt, getdate, cint
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip


class CustomSalarySlip(SalarySlip):
    """
    Salary Slip مخصص
    الهدف: 
    1. تجاهل الأقساط المدفوعة يدوياً (custom_is_paid = 1)
    2. منع إنشاء Loan Repayment Entry للقروض المدفوعة يدوياً
    """

    def validate(self):
        """Override validate مع تحقق نهائي"""
        super(CustomSalarySlip, self).validate()

        # ✅ CRITICAL: Force check if loans table is empty
        if not self.loans or len(self.loans) == 0:
            self.total_loan_repayment = 0
            self.total_principal_amount = 0
            self.total_interest_amount = 0

            frappe.logger().info(
                f"✅ {self.name}: No loans - forcing totals to ZERO"
            )
        else:
            # تسجيل تفاصيل القروض للـ debugging
            total_loan_amount = sum([flt(loan.total_payment)
                                    for loan in self.loans])
            frappe.logger().info(
                f"💵 Salary Slip {self.name} - Total Loan Deductions: {total_loan_amount} "
                f"from {len(self.loans)} loan(s)"
            )

    def on_submit(self):
        """
        🔥 CRITICAL OVERRIDE: منع إنشاء Loan Repayment Entry للقروض المدفوعة يدوياً
        """
        # ✅ التحقق من Net Pay
        if self.net_pay < 0:
            frappe.throw(_("Net Pay cannot be less than 0"))

        # ✅ تحديث الحالة
        self.set_status()
        self.update_status(self.name)

        # ✅ CRITICAL: Check if we should create Loan Repayment Entry
        should_create_loan_repayment = self._should_create_loan_repayment_entry()

        if should_create_loan_repayment:
            frappe.logger().info(
                f"✅ Creating Loan Repayment Entry for {self.name}"
            )
            self._make_loan_repayment_entry()
        else:
            frappe.logger().info(
                f"🚫 SKIPPED Loan Repayment Entry creation for {self.name}"
            )

        # ✅ إرسال الإيميل (إذا مطلوب)
        if not frappe.flags.via_payroll_entry and not frappe.flags.in_patch:
            email_salary_slip = cint(
                frappe.db.get_single_value(
                    "Payroll Settings", "email_salary_slip_to_employee")
            )
            if email_salary_slip:
                self.email_salary_slip()

        # ✅ تحديث حالة الدفع
        self.update_payment_status_for_gratuity_and_leave_encashment()

    def _should_create_loan_repayment_entry(self):
        """
        🔥 التحقق النهائي: هل يجب إنشاء Loan Repayment Entry؟

        Returns:
            bool: True إذا يجب الإنشاء, False إذا يجب التجاهل
        """
        # CHECK 1: Skip flag
        if flt(self.get("custom_skip_loan_repayment_creation")) == 1:
            frappe.logger().info(f"🚫 Skip flag set for {self.name}")
            return False

        # CHECK 2: Empty loans table
        if not self.get("loans") or len(self.loans) == 0:
            frappe.logger().info(f"🚫 No loans in {self.name}")
            return False

        # CHECK 3: Verify each loan is NOT paid manually
        valid_loans = []
        blocked_loans = []

        for loan_row in self.loans:
            # ✅ التحقق من Payment Entry يدوي
            has_manual_payment = frappe.db.sql("""
                SELECT COUNT(*) as count
                FROM `tabLoan Repayment` lr
                INNER JOIN `tabPayment Entry` pe ON pe.name = lr.payment_entry
                WHERE lr.against_loan = %s
                AND lr.docstatus = 1
                AND pe.docstatus = 1
                AND pe.custom_is_manual_loan_payment = 1
                AND lr.posting_date <= %s
            """, (loan_row.loan, self.posting_date))[0][0] or 0

            if has_manual_payment > 0:
                blocked_loans.append(loan_row.loan)
                frappe.logger().warning(
                    f"⚠️ BLOCKED: Loan {loan_row.loan} paid manually"
                )
                continue

            # ✅ التحقق من Active schedule
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
                blocked_loans.append(loan_row.loan)
                continue

            # ✅ التحقق من الأقساط غير المدفوعة
            unpaid_count = frappe.db.sql("""
                SELECT COUNT(*) as count
                FROM `tabRepayment Schedule` rs
                WHERE rs.parent = %s
                AND rs.parenttype = 'Loan Repayment Schedule'
                AND rs.payment_date BETWEEN %s AND %s
                AND (rs.custom_is_paid IS NULL OR rs.custom_is_paid = 0)
                AND rs.total_payment > IFNULL(rs.custom_paid_amount, 0)
            """, (active_schedule[0].name, self.start_date, self.end_date))[0][0] or 0

            if unpaid_count == 0:
                blocked_loans.append(loan_row.loan)
                frappe.logger().warning(
                    f"⚠️ BLOCKED: Loan {loan_row.loan} has no unpaid installments"
                )
                continue

            valid_loans.append(loan_row)

        # CHECK 4: Any valid loans left?
        if not valid_loans:
            frappe.logger().warning(
                f"🚫 FINAL BLOCK: All loans in {self.name} are either paid manually or fully paid"
            )

            # ✅ Update DB to prevent future attempts
            frappe.db.set_value(
                "Salary Slip",
                self.name,
                {
                    "custom_skip_loan_repayment_creation": 1,
                    "total_loan_repayment": 0,
                    "total_principal_amount": 0,
                    "total_interest_amount": 0
                },
                update_modified=False
            )
            frappe.db.commit()

            if blocked_loans:
                frappe.msgprint(
                    _("⚠️ Loan Repayment Entry NOT created.<br><br>"
                      "The following loans were paid manually via Payment Entry:<br>{0}").format(
                        "<br>".join(
                            [f"- <b>{loan}</b>" for loan in blocked_loans])
                    ),
                    alert=True,
                    indicator="orange",
                    title=_("Loans Already Paid")
                )

            return False

        return True

    def _make_loan_repayment_entry(self):
        """
        🔥 إنشاء Loan Repayment Entry (نسخة معدلة من الكود الأصلي)
        """
        try:
            from lending.loan_management.doctype.loan_repayment.loan_repayment import create_repayment_entry
            from erpnext.payroll.doctype.payroll_entry.payroll_entry import get_payroll_payable_account

            payroll_payable_account = get_payroll_payable_account(
                self.company, self.payroll_entry
            )

            process_payroll_accounting_entry_based_on_employee = frappe.db.get_single_value(
                "Payroll Settings", "process_payroll_accounting_entry_based_on_employee"
            )

            if not self.get("loans"):
                return

            for loan in self.get("loans", []):
                if not loan.total_payment:
                    continue

                # ✅ التحقق النهائي قبل إنشاء كل Loan Repayment
                has_manual_payment = frappe.db.sql("""
                    SELECT COUNT(*) as count
                    FROM `tabLoan Repayment` lr
                    INNER JOIN `tabPayment Entry` pe ON pe.name = lr.payment_entry
                    WHERE lr.against_loan = %s
                    AND lr.docstatus = 1
                    AND pe.docstatus = 1
                    AND pe.custom_is_manual_loan_payment = 1
                """, loan.loan)[0][0] or 0

                if has_manual_payment > 0:
                    frappe.logger().warning(
                        f"⚠️ SKIP: Loan {loan.loan} has manual payment - not creating repayment entry"
                    )
                    continue

                # ✅ إنشاء Loan Repayment Entry
                repayment_entry = create_repayment_entry(
                    loan.loan,
                    self.employee,
                    self.company,
                    self.posting_date,
                    loan.loan_product,
                    "Normal Repayment",
                    loan.interest_amount,
                    loan.principal_amount,
                    loan.total_payment,
                    payroll_payable_account=payroll_payable_account,
                    process_payroll_accounting_entry_based_on_employee=process_payroll_accounting_entry_based_on_employee,
                )

                repayment_entry.save()
                repayment_entry.submit()

                frappe.db.set_value(
                    "Salary Slip Loan",
                    loan.name,
                    "loan_repayment_entry",
                    repayment_entry.name
                )

                frappe.logger().info(
                    f"✅ Created Loan Repayment Entry {repayment_entry.name} for loan {loan.loan}"
                )

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"Error creating Loan Repayment Entry for {self.name}"
            )
            frappe.throw(
                _("Failed to create Loan Repayment Entry. Check Error Log for details.")
            )

    def get_loan_details(self):
        """
        ✅ ULTIMATE FIX: Override - جلب القروض من ACTIVE Schedule فقط
        ✅ تجاهل الأقساط المدفوعة يدوياً (عن طريق Payment Entry)
        """
        frappe.logger().info(
            f"🔍 Getting loan details for employee {self.employee}"
        )

        # ✅ STEP 1: جلب القروض اللي عندها ACTIVE Schedule فقط
        loans_with_active_schedule = frappe.db.sql("""
            SELECT DISTINCT
                l.name as loan,
                l.total_payment,
                l.total_amount_paid,
                l.monthly_repayment_amount,
                l.interest_income_account,
                l.loan_account,
                l.repayment_method,
                l.repayment_start_date,
                l.penalty_income_account,
                lrs.name as schedule_name
            FROM `tabLoan` l
            INNER JOIN `tabLoan Repayment Schedule` lrs ON lrs.loan = l.name
            WHERE 
                l.applicant = %s
                AND l.company = %s
                AND l.docstatus = 1
                AND lrs.status = 'Active'
                AND lrs.docstatus = 1
                AND l.repayment_method IN ('Repay Over Number of Periods', 'Repay Fixed Amount per Period')
        """, (self.employee, self.company), as_dict=True)

        frappe.logger().info(
            f"📋 Found {len(loans_with_active_schedule)} loans with Active schedules"
        )

        # ✅ STEP 2: لكل قرض، تحقق من وجود أقساط غير مدفوعة
        for loan_info in loans_with_active_schedule:
            # ✅ التحقق من Payment Entry يدوي
            has_manual_payment = frappe.db.sql("""
                SELECT COUNT(*) as count
                FROM `tabLoan Repayment` lr
                INNER JOIN `tabPayment Entry` pe ON pe.name = lr.payment_entry
                WHERE lr.against_loan = %s
                AND lr.docstatus = 1
                AND pe.docstatus = 1
                AND pe.custom_is_manual_loan_payment = 1
            """, loan_info.loan)[0][0] or 0

            if has_manual_payment > 0:
                frappe.logger().info(
                    f"⏭️ Skipping loan {loan_info.loan} - paid manually via Payment Entry"
                )
                continue

            # ✅ الحصول على الأقساط غير المدفوعة فقط في هذه الفترة
            pending_installments = self.get_pending_loan_installments(
                loan_info.loan,
                self.start_date,
                self.end_date
            )

            if pending_installments:
                frappe.logger().info(
                    f"✅ Adding loan {loan_info.loan} with {len(pending_installments)} pending installments"
                )
                # إضافة القرض للخصومات
                self.add_loan_to_salary_slip(loan_info, pending_installments)
            else:
                frappe.logger().info(
                    f"⏭️ Skipping loan {loan_info.loan} - no pending installments in this period"
                )

    def get_pending_loan_installments(self, loan_name, from_date, to_date):
        """
        ✅ ULTIMATE FIX: الحصول على الأقساط غير المدفوعة من ACTIVE Schedule فقط
        CRITICAL: يتحقق من custom_is_paid و custom_paid_amount
        """
        try:
            from_date = getdate(from_date)
            to_date = getdate(to_date)

            # ✅ الحصول على جدول السداد النشط
            active_schedule = frappe.db.sql("""
                SELECT name
                FROM `tabLoan Repayment Schedule`
                WHERE loan = %s
                AND status = 'Active'
                AND docstatus = 1
                ORDER BY posting_date DESC
                LIMIT 1
            """, loan_name, as_dict=1)

            if not active_schedule:
                frappe.logger().warning(
                    f"⚠️ No active Loan Repayment Schedule found for {loan_name}"
                )
                return []

            schedule_name = active_schedule[0].name

            # ✅ CRITICAL: الحصول على الأقساط غير المدفوعة في الفترة
            installments = frappe.db.sql("""
                SELECT 
                    rs.name,
                    rs.payment_date,
                    rs.principal_amount,
                    rs.interest_amount,
                    rs.total_payment,
                    rs.balance_loan_amount,
                    IFNULL(rs.custom_paid_amount, 0) as paid_amount,
                    IFNULL(rs.custom_is_paid, 0) as is_paid,
                    rs.custom_payment_reference
                FROM `tabRepayment Schedule` rs
                WHERE rs.parent = %s
                AND rs.parenttype = 'Loan Repayment Schedule'
                AND rs.payment_date BETWEEN %s AND %s
                ORDER BY rs.payment_date ASC
            """, (schedule_name, from_date, to_date), as_dict=1)

            pending_installments = []

            for schedule in installments:
                payment_date = getdate(schedule.payment_date)
                total_payment = flt(schedule.total_payment)
                paid_amount = flt(schedule.paid_amount)
                is_paid = schedule.is_paid

                # ✅ CRITICAL: إضافة فقط إذا لم يتم دفعه بالكامل
                if not is_paid and paid_amount < total_payment:
                    outstanding = total_payment - paid_amount

                    pending_installments.append({
                        'payment_date': schedule.payment_date,
                        'principal_amount': flt(schedule.principal_amount) * (outstanding / total_payment),
                        'interest_amount': flt(schedule.interest_amount) * (outstanding / total_payment),
                        'total_payment': outstanding,
                        'balance_loan_amount': flt(schedule.balance_loan_amount)
                    })

                    frappe.logger().info(
                        f"✅ Added unpaid installment: Date={payment_date}, Amount={outstanding}"
                    )

            return pending_installments

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"Error getting pending installments for {loan_name}"
            )
            return []

    def add_loan_to_salary_slip(self, loan_info, installments):
        """إضافة القرض للخصومات في Salary Slip"""
        try:
            total_principal = 0
            total_interest = 0

            for installment in installments:
                total_principal += flt(installment.get('principal_amount', 0))
                total_interest += flt(installment.get('interest_amount', 0))

            if total_principal > 0 or total_interest > 0:
                loan_component = self.get_loan_deduction_component()

                self.append('deductions', {
                    'salary_component': loan_component,
                    'amount': total_principal + total_interest,
                    'default_amount': total_principal + total_interest,
                })

                self.append('loans', {
                    'loan': loan_info.get('loan'),
                    'total_payment': total_principal + total_interest,
                    'interest_amount': total_interest,
                    'principal_amount': total_principal,
                    'loan_account': loan_info.get('loan_account'),
                    'interest_income_account': loan_info.get('interest_income_account')
                })

                frappe.logger().info(
                    f"✅ Added loan {loan_info.get('loan')} to Salary Slip: "
                    f"Principal={total_principal}, Interest={total_interest}"
                )

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"Error adding loan to salary slip"
            )

    def get_loan_deduction_component(self):
        """الحصول على أو إنشاء Salary Component للقرض"""
        component = frappe.db.get_value(
            "Salary Component",
            {"name": "Loan Repayment"},
            "name"
        )

        if not component:
            try:
                doc = frappe.get_doc({
                    "doctype": "Salary Component",
                    "salary_component": "Loan Repayment",
                    "salary_component_abbr": "LR",
                    "type": "Deduction",
                    "is_tax_applicable": 0
                })
                doc.insert(ignore_permissions=True)
                component = doc.name
            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title="Error creating Loan Repayment component"
                )
                component = "Loan Repayment"

        return component


# ========================================
# 🔥 Salary Slip Hooks
# ========================================

def prevent_duplicate_loan_deduction(doc, method):
    """
    ✅ ULTIMATE FIX: Check ACTIVE schedules + manual payments
    This runs BEFORE submit (in validate)
    """
    if not doc.employee:
        return

    frappe.logger().info(
        f"🔍 Pre-check loans for {doc.name} (Employee: {doc.employee})"
    )

    # ✅ Get loans with MANUAL payment (via Payment Entry)
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

    # ✅ Get loans with unpaid installments in ACTIVE schedule
    loans_with_unpaid = frappe.db.sql("""
        SELECT DISTINCT 
            lrs.loan,
            COUNT(rs.name) as unpaid_count
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

    # Filter out manually paid loans
    loans_with_unpaid = [
        loan for loan in loans_with_unpaid
        if loan.loan not in manual_loan_set
    ]

    if not loans_with_unpaid:
        doc.set("loans", [])
        doc.total_principal_amount = 0
        doc.total_interest_amount = 0
        doc.total_loan_repayment = 0
        doc.calculate_net_pay()
        doc.custom_skip_loan_repayment_creation = 1

        if manual_loan_set:
            frappe.msgprint(
                _("⚠️ القروض التالية تم دفعها يدوياً ولن يتم خصمها:<br>{0}").format(
                    "<br>".join(
                        [f"- <b>{loan}</b>" for loan in manual_loan_set])
                ),
                alert=True,
                indicator="blue",
                title=_("Loans Paid Manually")
            )
        return

    # Update loans table
    if doc.loans:
        valid_rows = []
        for row in doc.loans:
            if row.loan not in manual_loan_set:
                valid_rows.append(row)

        doc.set("loans", valid_rows)

        if not valid_rows:
            doc.total_principal_amount = 0
            doc.total_interest_amount = 0
            doc.total_loan_repayment = 0
            doc.calculate_net_pay()
            doc.custom_skip_loan_repayment_creation = 1
        else:
            doc.custom_skip_loan_repayment_creation = 0


def persist_skip_flag_on_submit(doc, method):
    """✅ Persist skip flag in DB after submit"""
    if doc.get("custom_skip_loan_repayment_creation") == 1:
        frappe.db.set_value(
            "Salary Slip",
            doc.name,
            "custom_skip_loan_repayment_creation",
            1,
            update_modified=False
        )
        frappe.db.commit()
