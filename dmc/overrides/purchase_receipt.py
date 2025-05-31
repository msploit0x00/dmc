from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt


class CustomPurchaseReceipt(PurchaseReceipt):
    def validate_with_previous_doc(self):
        # Call original validate() without calling validate_with_previous_doc
        # self.validate_supplier()
        # self.set_missing_values()
        # self.validate_accepted_rejected_qty()
        # self.validate_item_code()
        # self.validate_uom_is_integer("stock_uom", "stock_qty")
        # self.validate_for_subcontracting()
        # self.validate_item_rate()
        # self.set_expense_account()
        # self.set_cost_center()
        # self.check_qty()
        # self.validate_warehouse()
        # self.validate_with_previous_doc = lambda *args, **kwargs: None  # Just in case
        # self.validate_inspection()
        # self.validate_rejected_warehouse()
        # self.check_for_stopped_status()
        # self.check_qty_is_not_zero()
        # self.update_valuation_rate()
        # self.set_actual_qty()
        # self.make_barcode_doc()
        pass
