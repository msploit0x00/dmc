import frappe
from erpnext.payroll.doctype.salary_slip.salary_slip import make_loan_repayment_entry


def custom_make_loan_repayment_entry(doc):
    """
    Custom wrapper to skip loan repayment entry
    when the Salary Slip has no active loans.
    """
    if getattr(doc.flags, "skip_loan_repayment_entry", False):
        frappe.msgprint(
            "Skipping Loan Repayment Entry — no active loans for this employee.",
            alert=True,
            indicator="blue"
        )
        return None

    # Run normal ERPNext logic otherwise
    return make_loan_repayment_entry(doc)
