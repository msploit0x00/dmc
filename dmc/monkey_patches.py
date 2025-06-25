import erpnext.controllers.status_updater


def no_validate_actual_qty(self, sn_doc):
    # Disabled all core validations in this method as per user request
    pass


def apply_monkey_patches():
    from erpnext.stock.serial_batch_bundle import SerialBatchBundle
    SerialBatchBundle.validate_actual_qty = no_validate_actual_qty


def no_op_limits_crossed_error(self, args, item, qty_or_amount):
    # Bypass the over limit validation (do nothing)
    pass


erpnext.controllers.status_updater.StatusUpdater.limits_crossed_error = no_op_limits_crossed_error
