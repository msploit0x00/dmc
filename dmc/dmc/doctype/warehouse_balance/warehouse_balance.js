frappe.ui.form.on('Warehouse Balance', {
    refresh: function(frm) {
        frm.add_custom_button(__('Get Data'), function() {
            frm.call({
                method: 'get_stock_data',
                doc: frm.doc,
                freeze: true,
                callback: function(r) {
                    if (r.message) {
                        frm.refresh_field('items');  // Force refresh
                        frappe.msgprint("Stock data successfully fetched and added.");
                    }
                }
            });
        });
    }
});
