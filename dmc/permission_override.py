import frappe


from hr_sum_additionals.hr_sum_additionals.doctype.permission.permission import Permission
from hr_sum_additionals.hr_sum_additionals.doctype.penalties_rules.penalties_rules import get_the_rule



class CustomPermission(Permission):
    def on_submit(self):
        if self.docstatus == 1:
            get_the_rule(employee_id=self.employee,date=self.date,doctype=self.doctype,ref_docname=self.name)
