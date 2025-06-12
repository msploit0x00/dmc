frappe.ui.form.on('Delivery Note', {
    validate: function (frm) {
        const refMap = {};

        // Build a map of item_code to ref qty (from Ref table)
        frm.doc.custom_ref.forEach(ref => {
            if (ref.item_code) {
                refMap[ref.item_code] = ref.quantity; // <-- Use correct field name here
            }
        });

        const deliveryItemMap = {};

        // Sum up quantities in Delivery Note Items
        frm.doc.items.forEach(item => {
            if (item.item_code) {
                deliveryItemMap[item.item_code] = (deliveryItemMap[item.item_code] || 0) + item.qty;
            }
        });

        // Validate that each item in ref matches exactly in delivery items
        for (const [item_code, ref_qty] of Object.entries(refMap)) {
            const delivery_qty = deliveryItemMap[item_code] || 0;
            if (delivery_qty !== ref_qty) {
                frappe.throw(
                    `The total quantity for item ${item_code} must be exactly ${ref_qty}. Currently it is ${delivery_qty}.`
                );
            }
        }
    }
});
