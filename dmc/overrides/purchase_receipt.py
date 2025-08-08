from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from frappe.utils import flt, money_in_words
import frappe
from frappe import _


class CustomPurchaseReceipt(PurchaseReceipt):
    def validate_with_previous_doc(self):
        # Disabled all core validations in this method as per user request
        pass

    def limits_crossed_error(self, args, item, qty_or_amount):
        pass

    def validate_actual_qty(self, sn_doc):
        """Disable actual qty validation for serial/batch items"""
        pass

    def before_save(self):
        # Calculate base_amount for each item - Always use qty * base_rate
        for item in self.items:
            item.base_amount = flt(item.qty) * flt(item.base_rate)

    def validate(self):
        super().validate()

        # Fix purchase invoice item references
        self.fix_purchase_invoice_item_references()

        # Calculate and set total_qty
        self.total_qty = self.calculate_total_qty()

        # Set received_stock_qty if not set
        for item in self.items:
            if not item.received_stock_qty or item.received_stock_qty == 0:
                if item.qty and item.conversion_factor:
                    item.received_stock_qty = flt(
                        item.qty) * flt(item.conversion_factor)

    def fix_purchase_invoice_item_references(self):
        """Fix None purchase_invoice_item references by linking to correct PI items"""
        if not self.get("purchase_invoice"):
            return

        # Get Purchase Invoice Items
        pi_items = frappe.get_all("Purchase Invoice Item",
                                  filters={"parent": self.purchase_invoice},
                                  fields=["name", "item_code", "batch_no"])

        # Create a mapping of item_code + batch_no to PI item name
        pi_item_map = {}
        for pi_item in pi_items:
            key = f"{pi_item.item_code}_{pi_item.batch_no or ''}"
            pi_item_map[key] = pi_item.name

        # Update PR items with correct PI item references
        for pr_item in self.items:
            if not pr_item.purchase_invoice_item:
                key = f"{pr_item.item_code}_{pr_item.batch_no or ''}"
                if key in pi_item_map:
                    pr_item.purchase_invoice_item = pi_item_map[key]
                    # Update in database if document is saved
                    if not pr_item.get("__islocal"):
                        frappe.db.set_value("Purchase Receipt Item",
                                            pr_item.name,
                                            "purchase_invoice_item",
                                            pi_item_map[key])

    def on_submit(self):
        super().on_submit()

        # Ensure calculations are done on submit
        self.calculate_taxes_and_totals()
        self.set_rounded_total()
        self.set_in_words()
        self.total_qty = self.calculate_total_qty()

    def make_item_gl_entries(self, gl_entries, warehouse_account=None):
        """Override to handle None purchase_invoice_item values"""
        from erpnext.stock.utils import get_incoming_rate
        from erpnext.accounts.utils import get_account_currency

        stock_rbnb = self.get_company_default("stock_received_but_not_billed")
        landed_cost_entries = get_item_account_wise_additional_cost(self.name)
        expenses_included_in_valuation = self.get_company_default(
            "expenses_included_in_valuation")

        # Build net_rate_map safely, filtering out None values
        net_rate_map = {}
        if self.get("purchase_invoice"):
            for pi_item in frappe.get_all("Purchase Invoice Item",
                                          filters={
                                              "parent": self.purchase_invoice},
                                          fields=["name", "net_rate"]):
                net_rate_map[pi_item.name] = pi_item.net_rate

        def make_stock_received_but_not_billed_entry(item):
            # Check if purchase_invoice_item exists and is in the map
            if (item.purchase_invoice_item and
                item.purchase_invoice_item in net_rate_map and
                    item.net_rate == net_rate_map[item.purchase_invoice_item]):
                return 0

            account_currency = get_account_currency(stock_rbnb)
            credit_amount = (
                flt(item.base_net_amount, self.precision("base_net_amount"))
                if account_currency == self.company_currency
                else flt(item.net_amount, self.precision("net_amount"))
            )

            if credit_amount:
                gl_entries.append(
                    self.get_gl_dict(
                        {
                            "account": stock_rbnb,
                            "against": warehouse_account[item.warehouse]["account"],
                            "credit": credit_amount,
                            "credit_in_account_currency": credit_amount,
                            "cost_center": item.cost_center,
                            "project": item.project or self.project,
                            "voucher_detail_no": item.name,
                        },
                        account_currency,
                        item=item,
                    )
                )
            return credit_amount

        warehouse_with_no_account = []
        stock_items = self.get_stock_items()

        for item in self.get("items"):
            if flt(item.base_net_amount):
                if warehouse_account.get(item.warehouse):
                    stock_value_diff = get_incoming_rate(
                        {
                            "item_code": item.item_code,
                            "warehouse": item.warehouse,
                            "posting_date": self.posting_date,
                            "posting_time": self.posting_time,
                            "qty": item.stock_qty,
                            "serial_and_batch_bundle": item.get("serial_and_batch_bundle"),
                        },
                        raise_error_if_no_rate=False,
                    )

                    if stock_value_diff:
                        stock_value_diff *= item.stock_qty

                    warehouse_account_name = warehouse_account[item.warehouse]["account"]
                    warehouse_account_currency = warehouse_account[item.warehouse]["account_currency"]
                    supplier_warehouse_account = warehouse_account.get(
                        self.supplier_warehouse, {}).get("account")
                    supplier_warehouse_account_currency = warehouse_account.get(
                        self.supplier_warehouse, {}).get("account_currency")

                    if self.update_stock and item.valuation_rate:
                        gl_entries.append(
                            self.get_gl_dict(
                                {
                                    "account": warehouse_account_name,
                                    "against": supplier_warehouse_account or stock_rbnb,
                                    "cost_center": item.cost_center,
                                    "project": item.project or self.project,
                                    "remarks": self.get("remarks") or _("Accounting Entry for Stock"),
                                    "debit": stock_value_diff,
                                    "voucher_detail_no": item.name,
                                },
                                warehouse_account_currency,
                                item=item,
                            )
                        )

                        outgoing_amount = make_stock_received_but_not_billed_entry(
                            item)

                        if not outgoing_amount and stock_value_diff and not self.is_internal_transfer():
                            gl_entries.append(
                                self.get_gl_dict(
                                    {
                                        "account": stock_rbnb,
                                        "against": warehouse_account_name,
                                        "cost_center": item.cost_center,
                                        "project": item.project or self.project,
                                        "remarks": self.get("remarks") or _("Accounting Entry for Stock"),
                                        "credit": flt(stock_value_diff, self.precision("base_net_amount")),
                                        "voucher_detail_no": item.name,
                                    },
                                    item=item,
                                )
                            )

                elif item.item_code in stock_items:
                    warehouse_with_no_account.append(item.warehouse)

        if warehouse_with_no_account:
            frappe.msgprint(
                _("No accounting entries for the following warehouses {0}").format(
                    warehouse_with_no_account),
                title=_("Missing Account"),
            )

    def get_sl_entries(self, d, args):
        """
        Override to set custom rates PROPERLY at the source before SLE creation
        """
        # Get the standard SLE entry first
        sle = super().get_sl_entries(d, args)

        try:
            # Calculate the correct per-unit rate based on Purchase Receipt item data
            if d.conversion_factor and d.conversion_factor > 0:
                # For UOM conversions: base_rate is per UOM unit, need per stock_uom unit
                per_unit_rate = flt(d.base_rate) / flt(d.conversion_factor)
            else:
                # No conversion, base_rate is already per stock unit
                per_unit_rate = flt(d.base_rate)

            # Override the SLE rates BEFORE it's created
            sle.update({
                "incoming_rate": per_unit_rate,
                "valuation_rate": per_unit_rate,
            })

            # Calculate stock value difference based on actual quantity and our rate
            if sle.get("actual_qty"):
                sle["stock_value_difference"] = flt(
                    sle["actual_qty"]) * per_unit_rate

            print(
                f"DEBUG: Item {d.item_code} - Base Rate: {d.base_rate}, Conversion: {d.conversion_factor}, Per Unit Rate: {per_unit_rate}")

        except Exception as e:
            frappe.log_error(f"Error in custom get_sl_entries for item {d.item_code}: {str(e)}",
                             "Purchase Receipt Custom SLE Error")

        return sle

    def after_save(self):
        super().after_save()
        self.set_rounded_total()
        self.set_in_words()

    def update_total_amount(self):
        """Update base_total and save to database"""
        total = sum(flt(d.base_amount) for d in self.items)
        self.base_total = total
        self.db_set('base_total', total)

    def set_rounded_total(self):
        """Calculate and set rounded total"""
        if not self.disable_rounded_total:
            self.rounding_adjustment = flt(
                self.grand_total - self.rounded_total, self.precision("rounding_adjustment"))
            self.rounded_total = flt(
                self.grand_total, self.precision("rounded_total"))
            self.base_rounding_adjustment = flt(
                self.base_grand_total - self.base_rounded_total, self.precision("base_rounding_adjustment"))
            self.base_rounded_total = flt(
                self.base_grand_total, self.precision("base_rounded_total"))

    def set_in_words(self):
        """Set amount in words"""
        if self.rounded_total:
            self.in_words = money_in_words(self.rounded_total, self.currency)
        elif self.grand_total:
            self.in_words = money_in_words(self.grand_total, self.currency)

        # Always set base_in_words
        if self.base_rounded_total:
            self.base_in_words = money_in_words(
                self.base_rounded_total, self.company_currency)
        elif self.base_grand_total:
            self.base_in_words = money_in_words(
                self.base_grand_total, self.company_currency)

    def calculate_total_qty(self):
        """Calculate total_qty: if all UOMs are 'Unit', sum qty, else sum received_stock_qty."""
        if not self.items:
            return 0
        else:
            return sum(flt(item.received_stock_qty) for item in self.items)


def get_item_account_wise_additional_cost(purchase_document):
    """Get item account wise additional cost from landed cost voucher"""
    landed_cost_vouchers = frappe.get_all("Landed Cost Voucher",
                                          filters={
                                              "purchase_receipt": purchase_document},
                                          fields=["name"])

    item_account_wise_cost = {}
    for lcv in landed_cost_vouchers:
        lcv_doc = frappe.get_doc("Landed Cost Voucher", lcv.name)
        for item in lcv_doc.get("items"):
            item_account_wise_cost.setdefault(item.item_code, {})
            item_account_wise_cost[item.item_code].setdefault(
                item.expense_account, 0)
            item_account_wise_cost[item.item_code][item.expense_account] += flt(
                item.amount)

    return item_account_wise_cost
# from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
# from frappe.utils import flt, money_in_words
# import frappe
# from frappe import _


# class CustomPurchaseReceipt(PurchaseReceipt):
#     def validate_with_previous_doc(self):
#         # Disabled all core validations in this method as per user request
#         pass

#     def limits_crossed_error(self, args, item, qty_or_amount):
#         pass

#     def validate_actual_qty(self, sn_doc):
#         """Disable actual qty validation for serial/batch items"""
#         pass

#     def validate_with_previous_doc(self):
#         """Disable Purchase Order quantity validation"""
#         pass

#     def before_save(self):
#         for item in self.items:
#             if item.uom == 'Unit':
#                 item.base_amount = flt(item.qty) * flt(item.base_rate)
#             else:
#                 item.base_amount = flt(item.stock_qty) * flt(item.base_rate)

#     def validate(self):
#         super().validate()
#         # if self.custom_purchase_invoice_name:
#         #     self.fetch_invoice_data_for_items()
#         #     # Copy taxes and totals as before
#         #     try:
#         #         pinv = frappe.get_doc('Purchase Invoice',
#         #                               self.custom_purchase_invoice_name)
#         #         self.taxes = []
#         #         for tax in pinv.taxes:
#         #             self.append('taxes', tax.as_dict(copy=True))
#         #         # Set all totals from invoice
#         #         for field in [
#         #             'base_total', 'base_rounded_total', 'base_grand_total',
#         #             'grand_total', 'rounded_total', 'total', 'net_total', 'base_net_total',
#         #             'grand_total', 'rounded_total', 'base_grand_total', 'base_rounded_total'
#         #         ]:
#         #             setattr(self, field, getattr(pinv, field))
#         #         self.base_tax_withholding_net_total = 0
#         #         currency = getattr(self, "company_currency", None) or getattr(
#         #             self, "currency", None) or "EGP"
#         #         self.base_in_words = money_in_words(
#         #             self.base_rounded_total, currency)
#         #         if hasattr(pinv, 'in_words') and pinv.in_words:
#         #             self.in_words = pinv.in_words
#         #         if getattr(pinv, "custom_is_landed_cost", 0):
#         #             self.custom_shipment_order_name = getattr(
#         #                 pinv, "custom_shipment_name_ref", None)

#         #     except Exception as e:
#         #         frappe.log_error(
#         #             f"Error updating from purchase invoice: {str(e)}", "Purchase Receipt Update Error")
#         # else:
#         #     self.calculate_taxes_and_totals()
#         #     self.set_rounded_total()
#         #     self.set_in_words()
#         self.total_qty = self.calculate_total_qty()
#         self.db_set('total_qty', self.total_qty)
#         for item in self.items:
#             if not item.received_stock_qty or item.received_stock_qty == 0:
#                 if item.qty and item.conversion_factor:
#                     item.received_stock_qty = flt(
#                         item.qty) * flt(item.conversion_factor)

#     def on_submit(self):
#         super().on_submit()
#         # if self.custom_purchase_invoice_name:
#         #     self.fetch_invoice_data_for_items()
#         #     try:
#         #         pinv = frappe.get_doc('Purchase Invoice',
#         #                               self.custom_purchase_invoice_name)
#         #         # Set all totals from invoice
#         #         for field in [
#         #             'base_total', 'base_rounded_total', 'base_grand_total',
#         #             'grand_total', 'rounded_total', 'total', 'net_total', 'base_net_total',
#         #             'grand_total', 'rounded_total', 'base_grand_total', 'base_rounded_total'
#         #         ]:
#         #             setattr(self, field, getattr(pinv, field))
#         #         self.base_tax_withholding_net_total = 0
#         #         currency = getattr(self, "company_currency", None) or getattr(
#         #             self, "currency", None) or "EGP"
#         #         self.base_in_words = money_in_words(
#         #             self.base_rounded_total, currency)
#         #         if hasattr(pinv, 'in_words') and pinv.in_words:
#         #             self.in_words = pinv.in_words
#         #         self.total_qty = self.calculate_total_qty()
#         #         self.db_set('total_qty', self.total_qty)
#         #         self.db_set('base_tax_withholding_net_total', 0)
#         #         if getattr(pinv, "custom_is_landed_cost", 0):
#         #             self.custom_shipment_order_name = getattr(
#         #                 pinv, "custom_shipment_name_ref", None)
#         #     except Exception as e:
#         #         frappe.log_error(
#         #             f"Error in on_submit: {str(e)}", "Purchase Receipt Submit Error")
#         # else:
#         #     self.calculate_taxes_and_totals()
#         #     self.set_rounded_total()
#         #     self.set_in_words()
#         #     self.total_qty = self.calculate_total_qty()
#         #     self.db_set('total_qty', self.total_qty)
#         #     self.db_set('base_tax_withholding_net_total', 0)

#     def update_stock_ledger(self, allow_negative_stock=False, via_landed_cost_voucher=False):

#         from frappe.utils import flt

#         # Call the original method first - this creates all SLEs normally
#         super().update_stock_ledger(allow_negative_stock, via_landed_cost_voucher)

#         # Then update the rates with our Purchase Receipt base rates
#         try:
#             sle_list = frappe.get_all(
#                 "Stock Ledger Entry",
#                 filters={
#                     "voucher_type": "Purchase Receipt",
#                     "voucher_no": self.name,
#                     "is_cancelled": 0
#                 },
#                 fields=["name", "item_code", "batch_no",
#                         "actual_qty", "warehouse"]
#             )

#             for sle in sle_list:
#                 filters = {"parent": self.name, "item_code": sle.item_code}
#                 if sle.batch_no:
#                     filters["batch_no"] = sle.batch_no

#                 pr_base_rate = frappe.db.get_value(
#                     "Purchase Receipt Item", filters, "base_rate")

#                 if pr_base_rate:
#                     stock_value_diff = flt(sle.actual_qty) * flt(pr_base_rate)

#                     frappe.db.set_value("Stock Ledger Entry", sle.name, {
#                         "incoming_rate": pr_base_rate,
#                         "valuation_rate": pr_base_rate,
#                         "stock_value_difference": stock_value_diff
#                     })

#                     # Update bin valuation rate too
#                     bin_name = frappe.get_value("Bin",
#                                                 {"item_code": sle.item_code, "warehouse": sle.warehouse}, "name")
#                     if bin_name:
#                         frappe.db.set_value(
#                             "Bin", bin_name, "valuation_rate", pr_base_rate)

#             frappe.db.commit()

#         except Exception as e:
#             frappe.log_error(f"Error in custom update_stock_ledger: {str(e)}",
#                              "Purchase Receipt Custom Stock Ledger Error")

#     def get_sl_entries(self, d, args):
#         """
#         Override to set custom rates at the source before SLE creation
#         """
#         # Get the standard SLE entry
#         sle = super().get_sl_entries(d, args)

#         try:
#             # Override rates for Purchase Receipt
#             filters = {"parent": self.name, "item_code": d.item_code}
#             if hasattr(d, 'batch_no') and d.batch_no:
#                 filters["batch_no"] = d.batch_no

#             pr_base_rate = frappe.db.get_value(
#                 "Purchase Receipt Item", filters, "base_rate")

#             if pr_base_rate:
#                 sle.update({
#                     "incoming_rate": pr_base_rate,
#                     "valuation_rate": pr_base_rate,
#                 })

#                 if sle.get("actual_qty"):
#                     sle["stock_value_difference"] = flt(
#                         sle["actual_qty"]) * flt(pr_base_rate)

#         except Exception as e:
#             frappe.log_error(f"Error in custom get_sl_entries: {str(e)}",
#                              "Purchase Receipt Custom SLE Error")

#         return sle

#     def after_save(self):
#         super().after_save()
#         # if self.custom_purchase_invoice_name:
#         #     self.fetch_invoice_data_for_items()
#         #     try:
#         #         pinv = frappe.get_doc('Purchase Invoice',
#         #                               self.custom_purchase_invoice_name)
#         #         # Set all totals from invoice
#         #         for field in [
#         #             'base_total', 'base_rounded_total', 'base_grand_total',
#         #             'grand_total', 'rounded_total', 'total', 'net_total', 'base_net_total',
#         #             'grand_total', 'rounded_total', 'base_grand_total', 'base_rounded_total'
#         #         ]:
#         #             setattr(self, field, getattr(pinv, field))
#         #         self.base_tax_withholding_net_total = 0
#         #         currency = getattr(self, "company_currency", None) or getattr(
#         #             self, "currency", None) or "EGP"
#         #         self.base_in_words = money_in_words(
#         #             self.base_rounded_total, currency)
#         #         if hasattr(pinv, 'in_words') and pinv.in_words:
#         #             self.in_words = pinv.in_words
#         #         self.total_qty = self.calculate_total_qty()
#         #         self.db_set('total_qty', self.total_qty)
#         #         self.db_set('base_tax_withholding_net_total', 0)
#         #         if getattr(pinv, "custom_is_landed_cost", 0):
#         #             self.custom_shipment_order_name = getattr(
#         #                 pinv, "custom_shipment_name_ref", None)
#         #     except Exception as e:
#         #         frappe.log_error(
#         #             f"Error in after_save: {str(e)}", "Purchase Receipt After Save Error")
#         # else:
#         #     self.calculate_taxes_and_totals()
#         self.set_rounded_total()
#         self.set_in_words()
#         #     self.total_qty = self.calculate_total_qty()
#         #     self.db_set('total_qty', self.total_qty)
#         #     self.db_set('base_tax_withholding_net_total', 0)

#     def update_total_qty(self):
#         total = self.calculate_total_qty()
#         self.total_qty = total
#         self.db_set('total_qty', total)

#     def update_total_amount(self):
#         total = sum(flt(d.base_amount) for d in self.items)
#         self.base_total = total
#         self.db_set('base_total', total)

#     def set_rounded_total(self):
#         """Calculate and set rounded total"""
#         if not self.disable_rounded_total:
#             self.rounding_adjustment = flt(
#                 self.grand_total - self.rounded_total, self.precision("rounding_adjustment"))
#             self.rounded_total = flt(
#                 self.grand_total, self.precision("rounded_total"))
#             self.base_rounding_adjustment = flt(
#                 self.base_grand_total - self.base_rounded_total, self.precision("base_rounding_adjustment"))
#             self.base_rounded_total = flt(
#                 self.base_grand_total, self.precision("base_rounded_total"))

#     def set_in_words(self):
#         """Set amount in words"""
#         # Try to fetch from linked Purchase Invoice if available
#         if getattr(self, 'custom_purchase_invoice_name', None):
#             try:
#                 pinv = frappe.get_doc('Purchase Invoice',
#                                       self.custom_purchase_invoice_name)
#                 if hasattr(pinv, 'in_words') and pinv.in_words:
#                     self.in_words = pinv.in_words
#                 else:
#                     # fallback to rounded_total or grand_total
#                     if self.rounded_total:
#                         self.in_words = money_in_words(
#                             self.rounded_total, self.currency)
#                     elif self.grand_total:
#                         self.in_words = money_in_words(
#                             self.grand_total, self.currency)
#             except Exception:
#                 # fallback to rounded_total or grand_total
#                 if self.rounded_total:
#                     self.in_words = money_in_words(
#                         self.rounded_total, self.currency)
#                 elif self.grand_total:
#                     self.in_words = money_in_words(
#                         self.grand_total, self.currency)
#         else:
#             if self.rounded_total:
#                 self.in_words = money_in_words(
#                     self.rounded_total, self.currency)
#             elif self.grand_total:
#                 self.in_words = money_in_words(self.grand_total, self.currency)

#         # Always set base_in_words as before
#         if self.base_rounded_total:
#             self.base_in_words = money_in_words(
#                 self.base_rounded_total, self.company_currency)
#         elif self.base_grand_total:
#             self.base_in_words = money_in_words(
#                 self.base_grand_total, self.company_currency)

#     def fetch_stock_rate_uom(self):
#         """
#         This function loops through `items` in the given document,
#         fetches the matching item from linked Purchase Invoice,
#         and sets the stock_uom_rate and base_amount accordingly.
#         """
#         # if not self.items:
#         #     frappe.msgprint("No items found in the table.")
#         #     return

#         # for item in self.items:
#         #     if item.purchase_invoice:
#         #         try:
#         #             purchase_invoice = frappe.get_doc(
#         #                 "Purchase Invoice", item.purchase_invoice)
#         #             if purchase_invoice.items:
#         #                 # Find the matching item by item_code
#         #                 matched_item = next(
#         #                     (pi_item for pi_item in purchase_invoice.items if pi_item.item_code == item.item_code), None)

#         #                 if matched_item:
#         #                     item.stock_uom_rate = matched_item.rate
#         #                     item.base_amount = (
#         #                         item.base_rate or 0) * matched_item.rate
#         #                     self.base_total = item
#         #         except frappe.DoesNotExistError:
#         #             frappe.msgprint(
#         #                 f"Purchase Invoice {item.purchase_invoice} not found.")
#         #         except Exception as e:
#         #             frappe.log_error(frappe.get_traceback(),
#         #                              "Error in fetch_stock_rate_uom")

#     # def fetch_base_amount(self):
#     #     """
#     #     This function loops through items in the Purchase Receipt,
#     #     fetches the matching item from linked Purchase Invoice,
#     #     and sets the base_amount accordingly.
#     #     """
#     #     if not self.items:
#     #         frappe.msgprint("No items found in the table.")
#     #         return

#     #     for item in self.items:
#     #         if item.purchase_invoice:
#     #             try:
#     #                 purchase_invoice = frappe.get_doc(
#     #                     "Purchase Invoice", item.purchase_invoice)
#     #                 if purchase_invoice.items:
#     #                     # Find the matching item by item_code
#     #                     matched_item = next(
#     #                         (pi_item for pi_item in purchase_invoice.items if pi_item.item_code == item.item_code), None)

#     #                     if matched_item:
#     #                         # item.base_amount = matched_item.base_amount
#     #                         # Update total if needed
#     #                         # self.base_total = sum(
#     #                         #     item.base_amount for item in self.items)
#     #             except frappe.DoesNotExistError:
#     #                 frappe.msgprint(
#     #                     f"Purchase Invoice {item.purchase_invoice} not found.")
#     #             except Exception as e:
#     #                 frappe.log_error(frappe.get_traceback(),
#     #                                  "Error in fetch_base_amount")

#     # def set_base_amount_from_invoice(self):
#     #     # Only run if custom_purchase_invoice_name is set
#     #     if not getattr(self, 'custom_purchase_invoice_name', None):
#     #         return

#     #     try:
#     #         pinv = frappe.get_doc('Purchase Invoice',
#     #                               self.custom_purchase_invoice_name)
#     #     except frappe.DoesNotExistError:
#     #         frappe.msgprint(_("Purchase Invoice {0} not found.").format(
#     #             self.custom_purchase_invoice_name))
#     #         return

#     #     # Map item_code to Purchase Invoice Item
#     #     pinv_map = {item.item_code: item for item in pinv.items}

#     #     for item in self.items:
#     #         matched = pinv_map.get(item.item_code)
#     #         if matched:
#     #             item.base_rate = matched.base_rate
#     #             # item.base_amount = matched.base_amount
#     #             item.stock_uom_rate = matched.stock_uom_rate
#     #             # item.net_rate = matched.net_rate
#     #             # item.net_amount = matched.net_amount
#     #             # item.base_net_rate = matched.base_net_rate
#     #             # item.base_net_amount = matched.base_net_amount
#     #             item.purchase_invoice_item = matched.name

#     #     # Force recalculation of totals
#     #     self.calculate_taxes_and_totals()

#     # def fetch_invoice_data_for_items(self):
#     #     """
#     #     For each item in the Purchase Receipt, fetch matching data from the selected Purchase Invoice
#     #     and update the item's fields. For UOM 'Unit', set base_amount = base_rate * qty, and set all price fields from invoice.
#     #     Do NOT set received_stock_qty from invoice; always keep it from the receipt.
#     #     """
#     #     if not getattr(self, 'custom_purchase_invoice_name', None):
#     #         return

#     #     try:
#     #         pinv = frappe.get_doc('Purchase Invoice',
#     #                               self.custom_purchase_invoice_name)
#     #     except frappe.DoesNotExistError:
#     #         frappe.msgprint(_("Purchase Invoice {0} not found.").format(
#     #             self.custom_purchase_invoice_name))
#     #         return

#     #     if not pinv.items or not self.items:
#     #         return

#     #     for item in self.items:
#     #         matched = next(
#     #             (pi_item for pi_item in pinv.items if pi_item.item_code == item.item_code), None)
#     #         if matched:
#     #             item.base_rate = matched.base_rate
#     #             item.price_list_rate = getattr(matched, 'price_list_rate', 0)
#     #             item.base_price_list_rate = getattr(
#     #                 matched, 'base_price_list_rate', 0)
#     #             # if getattr(item, 'uom', None) == 'Unit':
#     #             #     item.base_amount = (
#     #             #         matched.base_rate or 0) * (item.qty or 0)
#     #             # else:
#     #             #     item.base_amount = (
#     #             #         matched.base_rate or 0) * (item.stock_qty or 0)
#     #             # item.stock_uom_rate = matched.stock_uom_rate
#     #             # item.net_rate = matched.net_rate
#     #             # item.net_amount = matched.net_amount
#     #             # item.base_net_rate = matched.base_net_rate
#     #             # item.base_net_amount = matched.base_net_amount
#     #             item.purchase_invoice_item = matched.name

#     def calculate_total_qty(self):
#         """Mimic the frontend logic for total_qty calculation: if all UOMs are 'Unit', sum qty, else sum received_stock_qty."""
#         all_unit = all(item.uom == "Unit" for item in self.items)
#         if all_unit:
#             return sum(flt(item.qty) for item in self.items)
#         else:
#             return sum(flt(item.received_stock_qty) for item in self.items)
