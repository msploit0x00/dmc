# ========================================
# الملف: dmc/overrides/salary_slip_edit.py
# ========================================

import frappe
from frappe import _
from frappe.utils import flt, getdate
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip


class CustomSalarySlip(SalarySlip):
    """
    Salary Slip مخصص
    الهدف: تجاهل الأقساط المدفوعة يدوياً (custom_is_paid = 1)
    """

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
            f"📋 Found {len(loans_with_active_schedule)} loans with Active schedules")

        # ✅ STEP 2: لكل قرض، تحقق من وجود أقساط غير مدفوعة
        for loan_info in loans_with_active_schedule:
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
                    f"⏭️ Skipping loan {loan_info.loan} - no pending installments in this period "
                    f"(all marked as paid via Payment Entry or Salary Slip)"
                )

    def get_pending_loan_installments(self, loan_name, from_date, to_date):
        """
        ✅ ULTIMATE FIX: الحصول على الأقساط غير المدفوعة من ACTIVE Schedule فقط
        CRITICAL: يتحقق من custom_is_paid و custom_paid_amount
        """
        try:
            from_date = getdate(from_date)
            to_date = getdate(to_date)

            frappe.logger().info(
                f"🔎 Checking installments for loan {loan_name} between {from_date} and {to_date}"
            )

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
            frappe.logger().info(f"📋 Found schedule: {schedule_name}")

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
                payment_ref = schedule.custom_payment_reference

                frappe.logger().info(
                    f"📅 Installment {payment_date}: Total={total_payment}, "
                    f"Paid={paid_amount}, Is_Paid={is_paid}, Ref={payment_ref}"
                )

                # ✅ CRITICAL: إضافة فقط إذا لم يتم دفعه بالكامل
                # سواء كان دفع يدوي (Payment Entry) أو من Salary Slip
                if not is_paid and paid_amount < total_payment:
                    outstanding = total_payment - paid_amount

                    pending_installments.append({
                        'payment_date': schedule.payment_date,
                        'principal_amount': flt(schedule.principal_amount) * (outstanding / total_payment),
                        'interest_amount': flt(schedule.interest_amount) * (outstanding / total_payment),
                        'total_payment': outstanding,  # المبلغ المتبقي فقط
                        'balance_loan_amount': flt(schedule.balance_loan_amount)
                    })

                    frappe.logger().info(
                        f"✅ Added unpaid installment: Date={payment_date}, Amount={outstanding}"
                    )
                else:
                    if is_paid:
                        ref_type = "Payment Entry" if payment_ref and "PAY-" in payment_ref else "Salary Slip"
                        frappe.logger().info(
                            f"⏭️ Skipped FULLY PAID installment: Date={payment_date}, "
                            f"Paid={paid_amount}/{total_payment}, Ref={payment_ref} ({ref_type})"
                        )
                    else:
                        frappe.logger().info(
                            f"⏭️ Skipped installment: Date={payment_date}"
                        )

            return pending_installments

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"Error getting pending installments for {loan_name}"
            )
            return []

    def add_loan_to_salary_slip(self, loan_info, installments):
        """
        إضافة القرض للخصومات في Salary Slip
        """
        try:
            total_principal = 0
            total_interest = 0

            for installment in installments:
                total_principal += flt(installment.get('principal_amount', 0))
                total_interest += flt(installment.get('interest_amount', 0))

            if total_principal > 0 or total_interest > 0:
                # الحصول على Salary Component للقرض
                loan_component = self.get_loan_deduction_component()

                # إضافة للخصومات
                self.append('deductions', {
                    'salary_component': loan_component,
                    'amount': total_principal + total_interest,
                    'default_amount': total_principal + total_interest,
                })

                # إضافة تفاصيل القرض
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
                    f"Principal={total_principal}, Interest={total_interest}, "
                    f"Total={total_principal + total_interest}"
                )

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"Error adding loan to salary slip"
            )

    def get_loan_deduction_component(self):
        """
        الحصول على أو إنشاء Salary Component للقرض
        """
        component = frappe.db.get_value(
            "Salary Component",
            {"name": "Loan Repayment"},
            "name"
        )

        if not component:
            # إنشاء إذا لم يكن موجوداً
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
                frappe.logger().info(
                    "✅ Created new Salary Component: Loan Repayment")
            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title="Error creating Loan Repayment component"
                )
                component = "Loan Repayment"  # Fallback

        return component

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
