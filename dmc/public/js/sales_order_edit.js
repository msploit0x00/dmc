

frappe.ui.form.on('Sales Team', {
    sales_person(frm, cdt, cdn) {
        sales_team_add_to_cost_center_allocation(frm, cdt, cdn);
    }
});
frappe.ui.form.on('Sales Team', {
    sales_person(frm, cdt, cdn) {
        sales_team_add_to_cost_center_allocation(frm, cdt, cdn);
    }
});


frappe.ui.form.on('Sales Order', {
    custom_sales_order_type(frm) {
        sales_order_type(frm);
        //   handle_tax_logic_from_address(frm);
    },

    custom_delivery_note_status(frm) { toggle_taxes_table(frm) },

    customer_address(frm) {
        handle_tax_logic_from_address(frm);
    },

    setup: function (frm) {
        // Only trigger on new (unsaved) forms
        if (frm.is_new()) {
            // Check if created from Partial Supply Order
            const from_doctype = frappe.get_prev_route()[0];
            const from_form = frappe.get_prev_route()[1];

            if (from_doctype === 'Partial Supply Order' && from_form) {
                // Set the custom field
                frm.set_value('custom_sales_order_type', 'امر بيع - هيئة الشراء الموحد');
            }
        }
    }
})

frappe.ui.form.on('Sales Order Item', {
    rate(frm, cdt, cdn) {
        rate_validation(frm, cdt, cdn)
    }
});

function sales_order_type(frm) {
    const type = frm.doc.custom_sales_order_type;

    if (type === "امر بيع - هيئة الشراء الموحد") {
        frm.set_value("customer", "1204010001");

    } else {
        frm.set_value("customer", "");
    }

    if (type === "أمر بيع -بيان") {
        // frm.set_df_property('custom_tax_status', 'hidden', 1);
        frm.set_df_property('taxes', 'hidden', 1);
        frm.set_df_property('total_taxes_and_charges', 'hidden', 1);

        frm.clear_table("taxes");
        frm.refresh_field("taxes");
    } else {
        // frm.set_df_property('custom_tax_status', 'hidden', 0);
        frm.set_df_property('taxes', 'hidden', 0);
        frm.set_df_property('total_taxes_and_charges', 'hidden', 0);
    }
}



function toggle_taxes_table(frm) {
    const is_taxable = frm.doc.custom_delivery_note_status === "خاضع";

    frm.toggle_display("taxes", is_taxable);
    if (frm.doc.custom_delivery_note_status === "معفي") {

        frm.set_df_property('taxes', 'hidden', 1);
        frm.set_df_property('tax_category', 'hidden', 1);
        frm.set_df_property('shipping_rule', 'hidden', 1);
        frm.set_df_property('incoterm', 'hidden', 1);
        frm.set_df_property('taxes_and_charges', 'hidden', 1);



        frm.set_df_property('total_taxes_and_charges', 'hidden', 1);
    } else {
        frm.set_df_property('total_taxes_and_charges', 'hidden', 0);
        frm.set_df_property('tax_category', 'hidden', 0);
        frm.set_df_property('shipping_rule', 'hidden', 0);
        frm.set_df_property('incoterm', 'hidden', 0);
        frm.set_df_property('taxes_and_charges', 'hidden', 0);



        frm.set_df_property('taxes', 'hidden', 0);


    }

    if (!is_taxable) {
        frm.clear_table("taxes");
        frm.refresh_field("taxes");

    }



}

async function handle_tax_logic_from_address(frm) {
    if (!frm.doc.customer_address) return;

    const address = await frappe.db.get_doc('Address', frm.doc.customer_address);

    if (address.custom_without_tax) {
        // معفي (Exempt)
        frm.toggle_display('taxes', false);
        frm.set_value('custom_delivery_note_status', 'معفي');
        // frm.set_value('custom_tax_status', 'Non-Taxable');

        frm.clear_table('taxes');
        frm.refresh_field('taxes');
    } else {
        // خاضع (Taxable)
        frm.toggle_display('taxes', true);
        frm.set_value('custom_delivery_note_status', 'خاضع');
        // frm.set_value('custom_tax_status', 'Taxable');

        if (!frm.doc.taxes || frm.doc.taxes.length === 0) {
            let row = frm.add_child('taxes');
            row.charge_type = 'On Net Total';
            // row.account_head = 'VAT - YourCompany'; // Replace with your actual account
            row.rate = 14; // Adjust as needed
            frm.refresh_field('taxes');
        }
    }
}



function rate_validation(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    // Skip if no item or invalid rate
    if (!row.item_code || row.rate === null || row.rate === undefined || row.rate === '') {
        return;
    }

    let rate_value = parseFloat(row.rate);
    if (isNaN(rate_value)) return;

    // OPTIONAL: Use Sales Order's price list if available
    let price_list = frm.doc.selling_price_list || 'Standard Selling';

    frappe.db.get_value('Item Price', {
        item_code: row.item_code,
        price_list: price_list
    }, 'price_list_rate').then(r => {
        if (r.message) {
            let actual_price = parseFloat(r.message.price_list_rate);
            console.log(`Item: ${row.item_code}, Price List Rate: ${actual_price}, Entered Rate: ${rate_value}`);

            if (rate_value < actual_price) {
                frappe.msgprint(__('Rate can\'t be lower than the actual price ({0})', [actual_price]));
                // Optional: Revert to null or actual price
                frappe.model.set_value(cdt, cdn, 'rate', actual_price);
            }
        } else {
            frappe.msgprint(__('No price found in Item Price for item {0} and price list {1}', [row.item_code, price_list]));
        }
    });
}

function sales_team_add_to_cost_center_allocation(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.sales_person) return;

    console.log("Fetching cost_center_allocation for", row.sales_person);

    frappe.call({
        method: "dmc.api.get_cost_center_allocation_naming_series",
        args: {
            sales_person: row.sales_person
        },
        callback: function (r) {
            if (r.message) {
                console.log("Backend response:", r.message);
                // ✅ Set field in the MAIN Sales Order form, not the row
                frm.set_value('cost_center_allocation', r.message);
            }
        }
    });
}