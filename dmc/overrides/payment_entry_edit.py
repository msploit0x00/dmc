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


# ========================================
# الملف: your_app_name/overrides/payment_entry.py
# الكود النهائي الصحيح بعد اكتشاف الـ Custom Fields
# ========================================

import frappe
from frappe import _
from frappe.utils import flt, getdate
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry


class CustomPaymentEntry(PaymentEntry):
    """
    Payment Entry مخصص
    الهدف: ربط Payment Entry بـ Loan Repayment وتحديث جدول الأقساط
    """

    def on_submit(self):
        """Override on_submit لإضافة منطق مخصص"""
        # استدعاء الدالة الأصلية أولاً - هذا ينشئ GL Entry
        super(CustomPaymentEntry, self).on_submit()

        # ثم ربط بـ Loan Repayment
        self.update_loan_repayment()

    def on_cancel(self):
        """Override on_cancel للتعامل مع loan repayment"""
        # إلغاء ربط Loan Repayment أولاً
        self.cancel_loan_repayment()

        # ثم استدعاء الدالة الأصلية - هذا يلغي GL Entry
        super(CustomPaymentEntry, self).on_cancel()

    def update_loan_repayment(self):
        """
        ربط Payment Entry بـ Loan Repayment بعد الحفظ
        ✅ يقوم فقط بالربط - GL Entry تم إنشاؤه بالفعل من Payment Entry
        """
        loan_repayment_name = self.get_loan_repayment_name()

        if loan_repayment_name:
            try:
                # 1. ربط Payment Entry بـ Loan Repayment
                frappe.db.set_value(
                    "Loan Repayment",
                    loan_repayment_name,
                    "payment_entry",
                    self.name
                )

                # 2. الحصول على Loan Repayment
                loan_repayment = frappe.get_doc(
                    "Loan Repayment", loan_repayment_name)

                frappe.msgprint(
                    _("تم ربط Payment Entry {0} بـ Loan Repayment {1}").format(
                        frappe.bold(self.name),
                        frappe.bold(loan_repayment_name)
                    ),
                    alert=True,
                    indicator="green"
                )

                # 3. ✅ تحديث جدول الأقساط (Repayment Schedule)
                if loan_repayment.against_loan:
                    self.mark_loan_schedule_as_paid(
                        loan_repayment.against_loan,
                        loan_repayment.amount_paid,
                        loan_repayment.posting_date
                    )

                    # تحديث حالة القرض
                    self.update_loan_closure_status(
                        loan_repayment.against_loan)

                frappe.db.commit()

            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title=f"خطأ في ربط Payment Entry بـ Loan Repayment {loan_repayment_name}"
                )
                frappe.throw(
                    _("خطأ أثناء الربط بـ Loan Repayment. تحقق من Error Log للتفاصيل."))

    def cancel_loan_repayment(self):
        """
        إلغاء ربط Payment Entry من Loan Repayment عند الإلغاء
        """
        loan_repayment_name = self.get_loan_repayment_name()

        if loan_repayment_name:
            try:
                # 1. الحصول على القرض قبل إلغاء الربط
                loan_repayment = frappe.get_doc(
                    "Loan Repayment", loan_repayment_name)
                against_loan = loan_repayment.against_loan

                # 2. ✅ إعادة جدول الأقساط
                if against_loan:
                    self.unmark_loan_schedule(
                        against_loan,
                        loan_repayment.amount_paid,
                        loan_repayment.posting_date
                    )

                # 3. إلغاء ربط Payment Entry من Loan Repayment
                frappe.db.set_value(
                    "Loan Repayment",
                    loan_repayment_name,
                    "payment_entry",
                    None
                )

                frappe.msgprint(
                    _("تم إلغاء ربط Payment Entry من Loan Repayment {0}").format(
                        frappe.bold(loan_repayment_name)
                    ),
                    alert=True,
                    indicator="orange"
                )

                # 4. تحديث حالة القرض
                if against_loan:
                    self.update_loan_closure_status(against_loan)

                frappe.db.commit()

            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title=f"خطأ في إلغاء ربط Loan Repayment {loan_repayment_name}"
                )

    def mark_loan_schedule_as_paid(self, loan_name, amount_paid, posting_date):
        """
        ✅ تعليم أقساط جدول السداد كمدفوعة (الأقدم أولاً)

        IMPORTANT: يستخدم custom_is_paid و custom_paid_amount
        (الـ Custom Fields الموجودة في النظام)
        """
        try:
            loan = frappe.get_doc("Loan", loan_name)
            remaining_amount = flt(amount_paid)
            posting_date = getdate(posting_date)

            # التحقق من وجود repayment_schedule
            if not hasattr(loan, 'repayment_schedule') or not loan.repayment_schedule:
                frappe.log_error(
                    message=f"Loan {loan_name} has no repayment_schedule",
                    title="Missing Repayment Schedule"
                )
                return

            # الحصول على الأقساط غير المدفوعة (الأقدم أولاً)
            unpaid_schedules = []
            for row in loan.repayment_schedule:
                # استخدم الـ Custom Fields الموجودة
                is_paid = row.get('custom_is_paid', 0)
                paid_amount = flt(row.get('custom_paid_amount', 0))
                total_payment = flt(row.get('total_payment', 0))

                # إذا لم يتم دفعه بالكامل
                if not is_paid and paid_amount < total_payment:
                    unpaid_schedules.append(row)

            # الترتيب حسب تاريخ الدفع
            unpaid_schedules.sort(key=lambda x: getdate(x.payment_date))

            for schedule in unpaid_schedules:
                if remaining_amount <= 0:
                    break

                paid_amount = flt(schedule.get('custom_paid_amount', 0))
                total_payment = flt(schedule.total_payment)
                outstanding = total_payment - paid_amount

                if outstanding <= 0:
                    continue

                # حساب المبلغ المراد دفعه لهذا القسط
                payment_for_schedule = min(remaining_amount, outstanding)

                # تحديث صف الجدول باستخدام Custom Fields
                new_paid_amount = paid_amount + payment_for_schedule
                schedule.custom_paid_amount = new_paid_amount

                # تعليم كمدفوع إذا تم الدفع بالكامل
                if flt(new_paid_amount) >= flt(total_payment):
                    schedule.custom_is_paid = 1

                # تسجيل معلومات الدفع
                schedule.custom_payment_reference = self.name
                schedule.custom_payment_date_actual = self.posting_date

                remaining_amount -= payment_for_schedule

                frappe.logger().info(
                    f"✅ تم تعليم القسط {schedule.payment_date} للقرض {loan_name}: "
                    f"مدفوع {new_paid_amount}/{total_payment}"
                )

            # حفظ القرض بدون تفعيل التحققات
            loan.flags.ignore_validate = True
            loan.flags.ignore_mandatory = True
            loan.save(ignore_permissions=True)

            frappe.msgprint(
                _("تم تحديث جدول سداد القرض بنجاح للقرض {0}").format(
                    frappe.bold(loan.name)
                ),
                alert=True,
                indicator="green"
            )

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"خطأ في تحديث جدول القرض لـ {loan_name}"
            )
            # لا ترمي exception عشان ما توقفش الـ Payment Entry
            frappe.msgprint(
                _("تحذير: لم يتم تحديث جدول السداد. تحقق من Error Log."),
                alert=True,
                indicator="orange"
            )

    def unmark_loan_schedule(self, loan_name, amount_paid, posting_date):
        """
        ✅ إعادة تغييرات الجدول عند إلغاء Payment Entry

        IMPORTANT: يستخدم custom_is_paid و custom_paid_amount
        """
        try:
            loan = frappe.get_doc("Loan", loan_name)
            remaining_amount = flt(amount_paid)
            posting_date = getdate(posting_date)

            if not hasattr(loan, 'repayment_schedule') or not loan.repayment_schedule:
                return

            # الحصول على الأقساط المدفوعة (الأحدث أولاً للعكس)
            paid_schedules = []
            for row in loan.repayment_schedule:
                is_paid = row.get('custom_is_paid', 0)
                paid_amount = flt(row.get('custom_paid_amount', 0))

                if is_paid or paid_amount > 0:
                    paid_schedules.append(row)

            # الترتيب حسب تاريخ الدفع (عكسي)
            paid_schedules.sort(key=lambda x: getdate(
                x.payment_date), reverse=True)

            for schedule in paid_schedules:
                if remaining_amount <= 0:
                    break

                paid_amount = flt(schedule.get('custom_paid_amount', 0))

                # حساب المبلغ المراد خصمه
                deduction = min(remaining_amount, paid_amount)

                # تحديث صف الجدول
                schedule.custom_paid_amount = paid_amount - deduction

                # إلغاء التعليم إذا لم يعد مدفوعاً بالكامل
                if flt(schedule.custom_paid_amount) < flt(schedule.total_payment):
                    schedule.custom_is_paid = 0

                # مسح معلومات الدفع
                if schedule.get('custom_payment_reference') == self.name:
                    schedule.custom_payment_reference = None
                    schedule.custom_payment_date_actual = None

                remaining_amount -= deduction

            # حفظ القرض
            loan.flags.ignore_validate = True
            loan.flags.ignore_mandatory = True
            loan.save(ignore_permissions=True)

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"خطأ في إعادة جدول القرض لـ {loan_name}"
            )

    def get_loan_repayment_name(self):
        """
        الحصول على اسم Loan Repayment من المراجع أو الحقل المخصص
        """
        # الطريقة 1: من جدول المراجع
        for ref in self.references:
            if ref.reference_doctype == "Loan Repayment":
                return ref.reference_name

        # الطريقة 2: من الحقل المخصص (إذا كان موجوداً)
        if hasattr(self, 'loan_repayment') and self.loan_repayment:
            return self.loan_repayment

        return None

    def update_loan_closure_status(self, loan_name):
        """
        تحديث حالة إغلاق القرض بناءً على إجمالي المدفوعات
        """
        try:
            loan = frappe.get_doc("Loan", loan_name)

            # حساب إجمالي المدفوع من جميع سندات السداد المحفوظة
            total_paid = frappe.db.sql("""
                SELECT IFNULL(SUM(amount_paid), 0)
                FROM `tabLoan Repayment`
                WHERE against_loan = %s
                AND docstatus = 1
            """, loan_name)[0][0]

            # التحقق إذا تم سداد القرض بالكامل
            if flt(total_paid) >= flt(loan.total_payment):
                if loan.status not in ["Loan Closure Requested", "Closed"]:
                    loan.db_set('status', 'Loan Closure Requested')
                    frappe.msgprint(
                        _("تم تعيين القرض {0} كـ 'مطلوب إغلاق القرض' (إجمالي المدفوع: {1})").format(
                            frappe.bold(loan.name),
                            frappe.bold(frappe.format_value(
                                total_paid, {"fieldtype": "Currency"}))
                        ),
                        alert=True,
                        indicator="green"
                    )
            else:
                # إذا تم وضع علامة إغلاق مسبقاً ولكن الدفع غير كافٍ الآن
                if loan.status == "Loan Closure Requested":
                    loan.db_set('status', 'Disbursed')
                    frappe.msgprint(
                        _("تم تغيير حالة القرض {0} إلى 'موزع' (المتبقي: {1})").format(
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
                title=f"خطأ في تحديث حالة إغلاق القرض لـ {loan_name}"
            )
    """
    Payment Entry مخصص
    الهدف: ربط Payment Entry بـ Loan Repayment وتحديث جدول الأقساط
    """

    def on_submit(self):
        """Override on_submit لإضافة منطق مخصص"""
        # استدعاء الدالة الأصلية أولاً - هذا ينشئ GL Entry
        super(CustomPaymentEntry, self).on_submit()

        # ثم ربط بـ Loan Repayment
        self.update_loan_repayment()

    def on_cancel(self):
        """Override on_cancel للتعامل مع loan repayment"""
        # إلغاء ربط Loan Repayment أولاً
        self.cancel_loan_repayment()

        # ثم استدعاء الدالة الأصلية - هذا يلغي GL Entry
        super(CustomPaymentEntry, self).on_cancel()

    def update_loan_repayment(self):
        """
        ربط Payment Entry بـ Loan Repayment بعد الحفظ
        ✅ يقوم فقط بالربط - GL Entry تم إنشاؤه بالفعل من Payment Entry
        """
        loan_repayment_name = self.get_loan_repayment_name()

        if loan_repayment_name:
            try:
                # 1. ربط Payment Entry بـ Loan Repayment
                frappe.db.set_value(
                    "Loan Repayment",
                    loan_repayment_name,
                    "payment_entry",
                    self.name
                )

                # 2. الحصول على Loan Repayment
                loan_repayment = frappe.get_doc(
                    "Loan Repayment", loan_repayment_name)

                frappe.msgprint(
                    _("تم ربط Payment Entry {0} بـ Loan Repayment {1}").format(
                        frappe.bold(self.name),
                        frappe.bold(loan_repayment_name)
                    ),
                    alert=True,
                    indicator="green"
                )

                # 3. ✅ جديد: تحديث جدول الأقساط
                if loan_repayment.against_loan:
                    self.mark_loan_schedule_as_paid(
                        loan_repayment.against_loan,
                        loan_repayment.amount_paid,
                        loan_repayment.posting_date
                    )

                    # تحديث حالة القرض
                    self.update_loan_closure_status(
                        loan_repayment.against_loan)

                frappe.db.commit()

            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title=f"خطأ في ربط Payment Entry بـ Loan Repayment {loan_repayment_name}"
                )
                frappe.throw(
                    _("خطأ أثناء الربط بـ Loan Repayment. تحقق من Error Log للتفاصيل."))

    def cancel_loan_repayment(self):
        """
        إلغاء ربط Payment Entry من Loan Repayment عند الإلغاء
        """
        loan_repayment_name = self.get_loan_repayment_name()

        if loan_repayment_name:
            try:
                # 1. الحصول على القرض قبل إلغاء الربط
                loan_repayment = frappe.get_doc(
                    "Loan Repayment", loan_repayment_name)
                against_loan = loan_repayment.against_loan

                # 2. ✅ جديد: إعادة جدول الأقساط
                if against_loan:
                    self.unmark_loan_schedule(
                        against_loan,
                        loan_repayment.amount_paid,
                        loan_repayment.posting_date
                    )

                # 3. إلغاء ربط Payment Entry من Loan Repayment
                frappe.db.set_value(
                    "Loan Repayment",
                    loan_repayment_name,
                    "payment_entry",
                    None
                )

                frappe.msgprint(
                    _("تم إلغاء ربط Payment Entry من Loan Repayment {0}").format(
                        frappe.bold(loan_repayment_name)
                    ),
                    alert=True,
                    indicator="orange"
                )

                # 4. تحديث حالة القرض
                if against_loan:
                    self.update_loan_closure_status(against_loan)

                frappe.db.commit()

            except Exception as e:
                frappe.log_error(
                    message=frappe.get_traceback(),
                    title=f"خطأ في إلغاء ربط Loan Repayment {loan_repayment_name}"
                )

    def mark_loan_schedule_as_paid(self, loan_name, amount_paid, posting_date):
        """
        ✅ تعليم أقساط جدول السداد كمدفوعة (الأقدم أولاً)
        هذا يمنع Salary Slip من محاولة خصم الأقساط المدفوعة بالفعل
        """
        try:
            loan = frappe.get_doc("Loan", loan_name)
            remaining_amount = flt(amount_paid)
            posting_date = getdate(posting_date)

            # الحصول على الأقساط غير المدفوعة (الأقدم أولاً)
            unpaid_schedules = [
                row for row in loan.repayment_schedule
                if not row.is_paid and flt(row.total_payment) > flt(row.paid_amount)
            ]

            # الترتيب حسب تاريخ الدفع
            unpaid_schedules.sort(key=lambda x: getdate(x.payment_date))

            for schedule in unpaid_schedules:
                if remaining_amount <= 0:
                    break

                outstanding = flt(schedule.total_payment) - \
                    flt(schedule.paid_amount)

                if outstanding <= 0:
                    continue

                # حساب المبلغ المراد دفعه لهذا القسط
                payment_for_schedule = min(remaining_amount, outstanding)

                # تحديث صف الجدول
                new_paid_amount = flt(
                    schedule.paid_amount) + payment_for_schedule
                schedule.paid_amount = new_paid_amount

                # تعليم كمدفوع إذا تم الدفع بالكامل
                if flt(new_paid_amount) >= flt(schedule.total_payment):
                    schedule.is_paid = 1

                remaining_amount -= payment_for_schedule

                frappe.logger().info(
                    f"تم تعليم جدول {schedule.payment_date} كمدفوع "
                    f"(مدفوع: {new_paid_amount}/{schedule.total_payment})"
                )

            # حفظ القرض بدون تفعيل التحققات
            loan.flags.ignore_validate = True
            loan.save(ignore_permissions=True)

            frappe.msgprint(
                _("تم تحديث جدول سداد القرض بنجاح للقرض {0}").format(
                    frappe.bold(loan.name)
                ),
                alert=True,
                indicator="green"
            )

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"خطأ في تحديث جدول القرض لـ {loan_name}"
            )

    def unmark_loan_schedule(self, loan_name, amount_paid, posting_date):
        """
        ✅ إعادة تغييرات الجدول عند إلغاء Payment Entry
        """
        try:
            loan = frappe.get_doc("Loan", loan_name)
            remaining_amount = flt(amount_paid)
            posting_date = getdate(posting_date)

            # الحصول على الأقساط المدفوعة (الأحدث أولاً للعكس)
            paid_schedules = [
                row for row in loan.repayment_schedule
                if row.is_paid or flt(row.paid_amount) > 0
            ]

            # الترتيب حسب تاريخ الدفع (عكسي)
            paid_schedules.sort(key=lambda x: getdate(
                x.payment_date), reverse=True)

            for schedule in paid_schedules:
                if remaining_amount <= 0:
                    break

                # حساب المبلغ المراد خصمه
                deduction = min(remaining_amount, flt(schedule.paid_amount))

                # تحديث صف الجدول
                schedule.paid_amount = flt(schedule.paid_amount) - deduction

                # إلغاء التعليم إذا لم يعد مدفوعاً بالكامل
                if flt(schedule.paid_amount) < flt(schedule.total_payment):
                    schedule.is_paid = 0

                remaining_amount -= deduction

            # حفظ القرض
            loan.flags.ignore_validate = True
            loan.save(ignore_permissions=True)

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"خطأ في إعادة جدول القرض لـ {loan_name}"
            )

    def get_loan_repayment_name(self):
        """
        الحصول على اسم Loan Repayment من المراجع أو الحقل المخصص
        """
        # الطريقة 1: من جدول المراجع
        for ref in self.references:
            if ref.reference_doctype == "Loan Repayment":
                return ref.reference_name

        # الطريقة 2: من الحقل المخصص (إذا كان موجوداً)
        if hasattr(self, 'loan_repayment') and self.loan_repayment:
            return self.loan_repayment

        return None

    def update_loan_closure_status(self, loan_name):
        """
        تحديث حالة إغلاق القرض بناءً على إجمالي المدفوعات
        """
        try:
            loan = frappe.get_doc("Loan", loan_name)

            # حساب إجمالي المدفوع من جميع سندات السداد المحفوظة
            total_paid = frappe.db.sql("""
                SELECT IFNULL(SUM(amount_paid), 0)
                FROM `tabLoan Repayment`
                WHERE against_loan = %s
                AND docstatus = 1
            """, loan_name)[0][0]

            # التحقق إذا تم سداد القرض بالكامل
            if flt(total_paid) >= flt(loan.total_payment):
                if loan.status not in ["Loan Closure Requested", "Closed"]:
                    loan.db_set('status', 'Loan Closure Requested')
                    frappe.msgprint(
                        _("تم تعيين القرض {0} كـ 'مطلوب إغلاق القرض' (إجمالي المدفوع: {1})").format(
                            frappe.bold(loan.name),
                            frappe.bold(frappe.format_value(
                                total_paid, {"fieldtype": "Currency"}))
                        ),
                        alert=True,
                        indicator="green"
                    )
            else:
                # إذا تم وضع علامة إغلاق مسبقاً ولكن الدفع غير كافٍ الآن
                if loan.status == "Loan Closure Requested":
                    loan.db_set('status', 'Disbursed')
                    frappe.msgprint(
                        _("تم تغيير حالة القرض {0} إلى 'موزع' (المتبقي: {1})").format(
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
                title=f"خطأ في تحديث حالة إغلاق القرض لـ {loan_name}"
            )
