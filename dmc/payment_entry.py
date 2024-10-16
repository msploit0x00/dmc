import frappe

from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry


class CustomPaymentEntry(PaymentEntry):
    def on_update_after_submit(self):

        proforma = self.custom_proforma_invoice_details

        ref = self.custom_reference__payment_



        for row in proforma:
            prof = frappe.get_doc("Proforma Invoice", row.proforma_invoice)
            prof.ignore_validate_update_after_submit = True
            prof.db_set('collection_amount', row.to_be_paid)

            self.append("custom_reference__payment_",{
            'proforma_invoice': row.proforma_invoice,
            'grand_total': row.grand_total,
            'to_be_paid': row.to_be_paid,
            'outstanding_amount': row.outstanding_amount
            })

            if prof.collection_amount == prof.grand_total:
                prof.db_set("fully_paid", 1)


        self.set("custom_proforma_invoice_details", [])

 


        frappe.msgprint("Proforma Updated Successfully")

