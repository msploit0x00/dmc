from datetime import date,timedelta

# from frappe.model.document import Document
# from frappe.utils import cint, get_datetime, get_time, getdate

# from erpnext.buying.doctype.supplier_scorecard.supplier_scorecard import daterange
# from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
# from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday

# from hrms.hr.doctype.attendance.attendance import mark_attendance
# from hrms.hr.doctype.employee_checkin.employee_checkin import (
#       calculate_working_hours,
#       mark_attendance_and_link_log,
# )
# from hrms.hr.doctype.shift_assignment.shift_assignment import get_employee_shift, get_shift_details

from hrms.hr.doctype.shift_type.shift_type import ShiftType
import requests
import frappe





def daily():
    shift_type = ShiftType
    allShiftnames = frappe.get_all('Shift Type')
    for shiftname in allShiftnames:
        frappe.db.set_value('Shift Type', shiftname, {
            'enable_auto_attendance': 1,
            'process_attendance_after': date.today() - timedelta(1),
            'last_sync_of_checkin': date.today()
        })
        doc = frappe.get_doc('Shift Type',shiftname)
        doc.reload()
        shift_type.process_auto_attendance(doc)
    
    return allShiftnames


