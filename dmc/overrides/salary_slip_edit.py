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
        frappe.logger().info(
            f"🔍 Getting loan details for employee {self.employee}"
        )

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
                AND l.status IN ('Disbursed', 'Partially Disbursed')
                AND l.repayment_method IN ('Repay Over Number of Periods', 'Repay Fixed Amount per Period')
        """, (self.employee, self.company), as_dict=True)

        frappe.logger().info(f"📋 Found {len(loans)} active loans")

        for loan_info in loans:
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
        ✅ الحصول على الأقساط غير المدفوعة فقط في فترة الراتب الحالية
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

            # ✅ الحصول على الأقساط غير المدفوعة في الفترة
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
                        frappe.logger().info(
                            f"⏭️ Skipped FULLY PAID installment: Date={payment_date}, "
                            f"Paid={paid_amount}/{total_payment}, Ref={payment_ref}"
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
                frappe.logger().info("✅ Created new Salary Component: Loan Repayment")
            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title="Error creating Loan Repayment component"
                )
                component = "Loan Repayment"

        return component

    def validate(self):
        """Override validate لإضافة تحققات مخصصة"""
        super(CustomSalarySlip, self).validate()

        if self.loans:
            total_loan_amount = sum([flt(loan.total_payment)
                                    for loan in self.loans])
            frappe.logger().info(
                f"💵 Salary Slip {self.name} - Total Loan Deductions: {total_loan_amount} "
                f"from {len(self.loans)} loan(s)"
            )
        else:
            frappe.logger().info(
                f"📭 Salary Slip {self.name} - No loans to deduct")

    def on_submit(self):
        """
        ✅ CRITICAL OVERRIDE: Use custom loan repayment logic
        """
        # ✅ Validation
        if self.net_pay < 0:
            frappe.throw(_("Net Pay cannot be less than 0"))

        # ✅ Set status
        self.set_status()
        self.update_status(self.name)

        # ✅ CRITICAL: Use our custom function instead of ERPNext's
        from dmc.overrides.loan_repayment_edit import custom_make_loan_repayment_entry
        custom_make_loan_repayment_entry(self)

        # ✅ Email salary slip
        if not frappe.flags.via_payroll_entry and not frappe.flags.in_patch:
            email_salary_slip = frappe.db.get_single_value(
                "Payroll Settings", "email_salary_slip_to_employee"
            )
            if email_salary_slip:
                self.email_salary_slip()

        # ✅ Update payment status
        self.update_payment_status_for_gratuity_and_leave_encashment()
