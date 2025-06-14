from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import SerialandBatchBundle


class CustomSerialandBatchBundle(SerialandBatchBundle):
    def validate_actual_qty(self, sn_doc):
        print("CustomSerialandBatchBundle.validate_actual_qty CALLED")
        # Disabled all core validations in this method as per user request
        pass
