import frappe

from hr_sum_additionals.hr_sum_additionals.doctype.penalties_rules.penalties_rules import get_the_rule

from hrms.hr.doctype.leave_application.leave_application import LeaveApplication



class CustomLeaveApplication(LeaveApplication):
    def on_submit(self):
        if self.docstatus == 1:
            posting_date = self.posting_date
            employee = self.employee
            doctype1 = self.doctype
            name1 = self.name

            get_the_rule(employee_id=employee,date=posting_date,doctype=doctype1,ref_docname=name1)
            msgprint("done")