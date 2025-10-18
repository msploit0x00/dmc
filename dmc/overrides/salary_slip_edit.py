# ========================================
# الملف: your_app_name/overrides/salary_slip.py
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
        ✅ Override: جلب تفاصيل القروض ولكن تجاهل الأقساط المدفوعة يدوياً
        """
        # الحصول على القروض النشطة للموظف
        loans = frappe.db.sql("""
            SELECT 
                l.name as loan,
                l.total_payment,
                l.total_amount_paid,
                l.monthly_repayment_amount,
                l.interest_income_account,
                l.loan_account,
                l.repayment_method,
                l.repayment_start_date,
                l.penalty_income_account
            FROM `tabLoan` l
            WHERE 
                l.applicant = %s
                AND l.company = %s
                AND l.docstatus = 1
                AND l.status = 'Disbursed'
                AND l.repayment_method IN ('Repay Over Number of Periods', 'Repay Fixed Amount per Period')
        """, (self.employee, self.company), as_dict=True)

        for loan_info in loans:
            # ✅ الحصول على الأقساط غير المدفوعة فقط في هذه الفترة
            pending_installments = self.get_pending_loan_installments(
                loan_info.loan,
                self.start_date,
                self.end_date
            )

            if pending_installments:
                # إضافة القرض للخصومات
                self.add_loan_to_salary_slip(loan_info, pending_installments)

    def get_pending_loan_installments(self, loan_name, from_date, to_date):
        """
        ✅ الحصول على الأقساط غير المدفوعة فقط في فترة الراتب الحالية

        CRITICAL: يتحقق من custom_is_paid
        """
        try:
            loan = frappe.get_doc("Loan", loan_name)

            # التحقق من وجود repayment_schedule
            if not hasattr(loan, 'repayment_schedule') or not loan.repayment_schedule:
                frappe.logger().info(
                    f"Loan {loan_name} has no repayment_schedule")
                return []

            pending_installments = []
            from_date = getdate(from_date)
            to_date = getdate(to_date)

            for schedule in loan.repayment_schedule:
                payment_date = getdate(schedule.payment_date)

                # التحقق إذا كان القسط في فترة الراتب الحالية
                if from_date <= payment_date <= to_date:
                    # ✅ CRITICAL: التحقق من custom_is_paid
                    is_paid = schedule.get('custom_is_paid', 0)
                    paid_amount = flt(schedule.get('custom_paid_amount', 0))
                    total_payment = flt(schedule.total_payment)

                    # إضافة فقط إذا لم يتم دفعه بالكامل
                    if not is_paid and paid_amount < total_payment:
                        outstanding = total_payment - paid_amount

                        pending_installments.append({
                            'payment_date': schedule.payment_date,
                            'principal_amount': flt(schedule.principal_amount),
                            'interest_amount': flt(schedule.interest_amount),
                            'total_payment': outstanding,  # المبلغ المتبقي فقط
                            'balance_loan_amount': flt(schedule.balance_loan_amount)
                        })

                        frappe.logger().info(
                            f"✅ Salary Slip {self.name}: Adding unpaid installment "
                            f"for {loan_name} - Date: {payment_date}, Amount: {outstanding}"
                        )
                    else:
                        frappe.logger().info(
                            f"⏭️  Salary Slip {self.name}: Skipping paid installment "
                            f"for {loan_name} - Date: {payment_date}, "
                            f"custom_is_paid: {is_paid}, paid: {paid_amount}/{total_payment}"
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
                # حساب المبلغ الأساسي والفائدة بشكل نسبي
                total_payment = flt(installment.get('total_payment', 0))
                original_principal = flt(
                    installment.get('principal_amount', 0))
                original_interest = flt(installment.get('interest_amount', 0))
                original_total = original_principal + original_interest

                if original_total > 0:
                    # حساب النسبة
                    principal_ratio = original_principal / original_total
                    interest_ratio = original_interest / original_total

                    # توزيع المبلغ المتبقي
                    total_principal += total_payment * principal_ratio
                    total_interest += total_payment * interest_ratio
                else:
                    total_principal += total_payment

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
                    f"✅ Added loan {loan_info.get('loan')} to Salary Slip {self.name}: "
                    f"Principal: {total_principal}, Interest: {total_interest}"
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
            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title="Error creating Loan Repayment component"
                )
                component = "Loan Repayment"  # Fallback

        return component

    def validate(self):
        """Override validate لإضافة تحققات مخصصة"""
        super(CustomSalarySlip, self).validate()

        # تسجيل تفاصيل القروض للـ debugging
        if self.loans:
            total_loan_amount = sum([flt(loan.total_payment)
                                    for loan in self.loans])
            frappe.logger().info(
                f"Salary Slip {self.name} - Total Loan Deductions: {total_loan_amount} "
                f"from {len(self.loans)} loan(s)"
            )
