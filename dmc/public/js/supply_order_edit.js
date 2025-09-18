// Supply Order form events
frappe.ui.form.on('Supply order', {
    refresh(frm) {
        // Check tax status when form loads
        check_customer_tax_status(frm);
    },

    party_name(frm) {
        // Check tax status when party_name (customer) changes
        check_customer_tax_status(frm);
    },

    onload(frm) {
        // Check tax status when form loads initially
        setTimeout(() => {
            check_customer_tax_status(frm);
        }, 1000);
    },

    after_save(frm) {
        // Check tax status after save
        check_customer_tax_status(frm);
    }
});

// Function to check customer tax status and toggle tax fields
async function check_customer_tax_status(frm) {
    if (!frm.doc.party_name) {
        // If no customer selected, show tax fields by default
        toggle_supply_order_taxes_table(frm, true);
        return;
    }

    try {
        // Get customer document to check custom_item_tax_template
        const customer = await frappe.db.get_doc('Customer', frm.doc.party_name);

        // Check if customer has custom_item_tax_template value
        const has_tax_template = customer.custom_item_tax_template &&
            customer.custom_item_tax_template.trim() !== '';

        console.log('Customer:', frm.doc.party_name);
        console.log('Tax Template:', customer.custom_item_tax_template);
        console.log('Has Tax Template:', has_tax_template);

        if (has_tax_template) {
            // خاضع للضريبة (Taxable) - Show taxes
            console.log('Customer is taxable - showing taxes');
            toggle_supply_order_taxes_table(frm, true);
        } else {
            // غير خاضع للضريبة (Non-taxable) - Hide taxes
            console.log('Customer is non-taxable - hiding taxes');
            toggle_supply_order_taxes_table(frm, false);
        }
    } catch (error) {
        console.error('Error checking customer tax status:', error);
        // Default to showing taxes in case of error
        toggle_supply_order_taxes_table(frm, true);
    }
}

// Function to toggle tax table and related fields visibility
function toggle_supply_order_taxes_table(frm, is_taxable) {
    console.log('Toggling taxes table. Is taxable:', is_taxable);

    if (is_taxable) {
        // Shois_taxablew tax fields - خاضع للضريبة
        frm.set_df_property('taxes', 'hidden', 0);
        frm.set_df_property('tax_category', 'hidden', 0);
        frm.set_df_property('shipping_rule', 'hidden', 0);
        frm.set_df_property('taxes_and_charges', 'hidden', 0);
        frm.set_df_property('total_taxes_and_charges', 'hidden', 0);
        frm.set_df_property('incoterm', 'hidden', 0);

        // Show taxes section
        frm.toggle_display("taxes", true);

        // Refresh the form to show changes
        frm.refresh_fields();

    } else {
        // Hide tax fields - غير خاضع للضريبة
        frm.set_df_property('taxes', 'hidden', 1);
        frm.set_df_property('tax_category', 'hidden', 1);
        frm.set_df_property('shipping_rule', 'hidden', 1);
        frm.set_df_property('taxes_and_charges', 'hidden', 1);
        frm.set_df_property('total_taxes_and_charges', 'hidden', 1);
        frm.set_df_property('incoterm', 'hidden', 1);

        // Hide taxes section
        frm.toggle_display("taxes", false);

        // Clear taxes table to exclude from calculation
        frm.clear_table("taxes");
        frm.refresh_field("taxes");

        // Clear tax-related fields
        frm.set_value('tax_category', '');
        frm.set_value('taxes_and_charges', '');

        // Refresh the form to show changes
        frm.refresh_fields();
    }
}