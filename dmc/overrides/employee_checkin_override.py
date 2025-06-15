
import frappe
from datetime import datetime, time, timedelta
from hrms.hrms.hr.doctype.employee_checkin.employee_checkin import EmployeeCheckin


class CustomEmployeeCheckin(EmployeeCheckin):
    def after_insert(self):
        self.calculate_deduction()

    def onload(self):
        self.calculate_deduction()

    def calculate_deduction(self):
        if not self.employee or not self.time or not self.log_type:
            return

        emp = frappe.get_doc("Employee", self.employee)
        if not emp.default_shift:
            return

        shift = frappe.get_doc("Shift Type", emp.default_shift)

        shift_time_raw = shift.start_time if self.log_type == "IN" else shift.end_time
        if not shift_time_raw:
            return

        check_time = self.time

        if isinstance(shift_time_raw, time):
            shift_time = datetime.combine(check_time.date(), shift_time_raw)
        elif isinstance(shift_time_raw, timedelta):
            shift_time = datetime.combine(
                check_time.date(), (datetime.min + shift_time_raw).time())
        elif isinstance(shift_time_raw, str):
            shift_time = datetime.strptime(shift_time_raw, "%H:%M:%S").replace(
                year=check_time.year, month=check_time.month, day=check_time.day
            )
        else:
            return

        diff_in_minutes = int((check_time - shift_time).total_seconds() / 60)

        abs_minutes = abs(diff_in_minutes)
        human_hours = abs_minutes // 60
        human_minutes = abs_minutes % 60

        if diff_in_minutes > 0:
            arabic_text = f"متأخر: {human_hours} ساعة و {human_minutes} دقيقة"
        elif diff_in_minutes < 0:
            arabic_text = f"مبكر: {human_hours} ساعة و {human_minutes} دقيقة"
        else:
            arabic_text = "في الموعد تمامًا"

        self.custom_deduction = diff_in_minutes
        self.custom_deduction_text = arabic_text
        self.start_time = shift.start_time
        self.end_time = shift.end_time
