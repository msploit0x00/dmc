frappe.ui.form.on('Sales Team', {
    sales_person(frm, cdt, cdn) {
        sales_team_add_to_cost_center_allocation(frm, cdt, cdn);
    }
});

frappe.ui.form.on('Sales Order', {

    custom_sales_order_type(frm) {
        sales_order_type_onchange(frm);
    },

    onload(frm) {
        if (frm.doc.custom_sub_number) {
            setTimeout(function () {
                frm.set_value('custom_sales_order_type', 'امر بيع - هيئة الشراء الموحد');
                frm.set_df_property('custom_sales_order_type', 'read_only', 1);
                frm.set_df_property('customer', 'read_only', 1);
            }, 400);
        }
        handle_tax_logic_from_address(frm);
    },

    after_save(frm) {
        sales_order_type_aftersave(frm);
    },

    custom_delivery_note_status(frm) {
        toggle_taxes_table(frm)
    },

    customer_address(frm) {
        handle_tax_logic_from_address(frm);
    },
})

frappe.ui.form.on('Sales Order Item', {
    price_list_rate(frm, cdt, cdn) {
        rate_validation(frm, cdt, cdn)
    },

    is_free_item: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.is_free_item) {
            console.log('🎁 Free item detected, setting discount to 100%');
            frappe.model.set_value(cdt, cdn, 'margin_type', 'Percentage');
            frappe.model.set_value(cdt, cdn, 'discount_percentage', 100);

            frappe.show_alert({
                message: __('Free item: 100% discount applied'),
                indicator: 'green'
            });
        } else {
            frappe.model.set_value(cdt, cdn, 'discount_percentage', 0);
        }
    },
});

function sales_order_type_onchange(frm) {
    const type = frm.doc.custom_sales_order_type;

    // Only set customer based on type
    if (type === "امر بيع - هيئة الشراء الموحد") {
        frm.set_value("customer", "1204010001");
    } else {
        frm.set_value("customer", "");
    }

    // Set Delivery Note Type based on Sales Order Type
    if (type === "أمر بيع -بيان") {
        frm.set_value("custom_delivery_note_type", "اذن صرف مبيعات نقدى");

        // ✅ FORCE TAX CATEGORY TO معفي FOR أمر بيع -بيان
        frm.set_value("tax_category", "معفي");
        frm.set_value("custom_delivery_note_status", "معفي");

        // Clear taxes table
        frm.clear_table("taxes");
        frm.refresh_field("taxes");
    } else {
        frm.set_value("custom_delivery_note_type", "اذن صرف مبيعات أجلة");

        // For other types, check address tax logic
        handle_tax_logic_from_address(frm);
    }

    // Apply visibility logic
    apply_tax_visibility_logic(frm, type);
}

function sales_order_type_aftersave(frm) {
    const type = frm.doc.custom_sales_order_type;
    apply_tax_visibility_logic(frm, type);
}

function apply_tax_visibility_logic(frm, type) {
    const hideTaxFields = (type === "أمر بيع -بيان");

    frm.set_df_property('taxes', 'hidden', hideTaxFields);
    frm.set_df_property('total_taxes_and_charges', 'hidden', hideTaxFields);
    frm.set_df_property('tax_category', 'hidden', hideTaxFields);
    frm.set_df_property('shipping_rule', 'hidden', hideTaxFields);
    frm.set_df_property('incoterm', 'hidden', hideTaxFields);
    frm.set_df_property('taxes_and_charges', 'hidden', hideTaxFields);

    if (hideTaxFields) {
        frm.clear_table("taxes");
        frm.refresh_field("taxes");
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
    const type = frm.doc.custom_sales_order_type;

    // ✅ IF Sales Order Type is "أمر بيع -بيان", ALWAYS SET معفي (Override Customer tax_category)
    if (type === "أمر بيع -بيان") {
        console.log("✅ Sales Order Type is 'أمر بيع -بيان' - Setting tax_category to 'معفي' regardless of Customer");
        frm.set_value("tax_category", "معفي");
        frm.set_value("custom_delivery_note_status", "معفي");
        frm.toggle_display('taxes', false);
        frm.clear_table('taxes');
        frm.refresh_field('taxes');
        return; // Exit early, ignore customer and address tax logic
    }

    // ✅ For other order types, check customer tax_category first
    if (frm.doc.customer) {
        const customer = await frappe.db.get_doc('Customer', frm.doc.customer);

        // If customer has tax_category = "خاضع", set it
        if (customer.tax_category === "خاضع") {
            frm.set_value('custom_delivery_note_status', 'خاضع');
            frm.toggle_display('taxes', true);
            return;
        }
    }

    // ✅ If customer doesn't have tax_category, check address
    if (!frm.doc.customer_address) return;

    const address = await frappe.db.get_doc('Address', frm.doc.customer_address);

    if (address.custom_without_tax) {
        // معفي (Exempt)
        frm.toggle_display('taxes', false);
        frm.set_value('custom_delivery_note_status', 'معفي');
        frm.set_value("tax_category", "معفي");
        frm.clear_table('taxes');
        frm.refresh_field('taxes');
    } else {
        // خاضع (Taxable)
        frm.toggle_display('taxes', true);
        frm.set_value('custom_delivery_note_status', 'خاضع');
    }
}

function rate_validation(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    // ✅ CASE 1: SKIP VALIDATION IF is_free_item IS CHECKED
    if (row.is_free_item) {
        console.log('✅ is_free_item is checked - skipping rate validation');
        return;
    }

    // ✅ CASE 2: SKIP VALIDATION IF THERE'S A DISCOUNT OR MARGIN
    if (row.discount_percentage > 0 || row.discount_amount > 0) {
        console.log('✅ Discount applied - skipping rate validation');
        return;
    }

    if (row.margin_type && row.margin_type !== '') {
        console.log('✅ Margin type selected - skipping rate validation');
        return;
    }

    // Skip if no item or invalid price_list_rate
    if (!row.item_code || row.price_list_rate === null || row.price_list_rate === undefined || row.price_list_rate === '') {
        return;
    }

    let price_list_rate_value = parseFloat(row.price_list_rate);
    if (isNaN(price_list_rate_value)) return;

    let price_list = frm.doc.selling_price_list || 'Standard Selling';

    frappe.db.get_value('Item Price', {
        item_code: row.item_code,
        price_list: price_list
    }, 'price_list_rate').then(r => {
        if (r.message) {
            let actual_price = parseFloat(r.message.price_list_rate);
            console.log(`Item: ${row.item_code}, Price List Rate: ${actual_price}, Entered Price List Rate: ${price_list_rate_value}`);

            if (price_list_rate_value < actual_price) {
                frappe.msgprint(__('Rate can\'t be lower than the actual price ({0})', [actual_price]));
                frappe.model.set_value(cdt, cdn, 'price_list_rate', actual_price);
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
                frm.set_value('cost_center_allocation', r.message);
            }
        }
    });
}