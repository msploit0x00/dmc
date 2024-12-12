frappe.provide("erpnext.stock");
frappe.provide("erpnext.accounts.dimensions");

frappe.ui.form.on("Stock Reconciliation", {
	custom_barcode(frm) {
    frappe.call({
      method:"dmc.stock_reconcilition_override.getConv_factor_for_uom",
      args:{
        barcode:frm.doc.custom_barcode
      },
      callback:function(res){
        console.log("response",res.message)
      }
    })
  }
})