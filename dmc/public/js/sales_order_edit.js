frappe.ui.form.on('Sales Order Item', {
    rate: function(frm, cdt, cdn) {
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
});

frappe.ui.form.on('Sales Order', {
	custom_sales_order_type(frm) {
	  sales_order_type(frm);
    //   handle_tax_logic_from_address(frm);
	},

    custom_tax_status(frm){ toggle_taxes_table(frm)},

       customer_address(frm) {
        handle_tax_logic_from_address(frm);
    },
    
    



    //  customer_address: async function(frm) {
    //     if (!frm.doc.customer_address) return;

    //     // Fetch the linked Address document
    //     await frappe.db.get_doc('Address', frm.doc.customer_address)
    //         .then(address => {
    //             if (address.custom_without_tax) {
    //                 // Case: معفي / Non-Taxable
    //                 frm.toggle_display('taxes', false); // Hide taxes table
    //                 frm.set_value('custom_delivery_note_status', 'معفي');
    //                 frm.set_value('custom_tax_status', 'Non-Taxable');

    //                 frm.clear_table('taxes'); // Optional: remove existing tax rows
    //                 frm.refresh_field('taxes');
    //             } else {
    //                 // Case: خاضع / Taxable
    //                 frm.toggle_display('taxes', true); // Show taxes table
    //                 frm.set_value('custom_delivery_note_status', 'خاضع');
    //                 frm.set_value('custom_tax_status', 'Taxable');

    //                 // // Add a default tax row if empty
    //                 // if (!frm.doc.taxes || frm.doc.taxes.length === 0) {
    //                 //     let row = frm.add_child('taxes');
    //                 //     row.charge_type = 'On Net Total';
    //                 //     row.account_head = 'VAT - YourCompany'; // Replace with your actual account
    //                 //     row.rate = 14; // Example tax rate
    //                 //     frm.refresh_field('taxes');
    //                 // }
    //             }
    //         });
    // }
       
})





function sales_order_type(frm) {
    const type = frm.doc.custom_sales_order_type;

    if (type === "امر بيع - هيئة الشراء الموحد") {
        frm.set_value("customer", "1204010001");

        // Optional: clear address
        // frm.set_value("customer_address", "");
        // frm.refresh_field("customer");

    } else {
        frm.set_value("customer", "");
    }

    if (type === "أمر بيع -بيان") {
        frm.set_df_property('custom_tax_status', 'hidden', 1);
        frm.set_df_property('taxes', 'hidden', 1);
        frm.set_df_property('total_taxes_and_charges', 'hidden', 1);

        frm.clear_table("taxes");
        frm.refresh_field("taxes");
    } else {
        frm.set_df_property('custom_tax_status', 'hidden', 0);
        frm.set_df_property('taxes', 'hidden', 0);
        frm.set_df_property('total_taxes_and_charges', 'hidden', 0);
    }
}


// function sales_order_type(frm) {
//      if(frm.doc.custom_sales_order_type === "امر بيع - هيئة الشراء الموحد"){
// 	        frm.set_value("customer", "1204010001")
            
// 	       // frm.set_value("customer_address","")
// 	       // frm.refresh_field("customer")
// 	    } else{
// 	        frm.set_value("customer", "")
// 	    }
//         if(frm.doc.custom_sales_order_type === "أمر بيع -بيان"){

            
//             frm.set_df_property('custom_tax_status', 'hidden', 1);
//             frm.set_df_property('taxes', 'hidden', 1);

//             frm.set_df_property('total_taxes_and_charges', 'hidden', 1);

//             frm.clear_table("taxes");
//             frm.refresh_field("taxes");
        
//         } else{
//             frm.set_df_property('custom_tax_status', 'hidden', 0);

//             frm.set_df_property('taxes', 'hidden', 0);

//             frm.set_df_property('total_taxes_and_charges', 'hidden', 0);
//         }

// }




function toggle_taxes_table(frm) {
    const is_taxable = frm.doc.custom_tax_status === "Taxable";

    frm.toggle_display("taxes", is_taxable);
    if (frm.doc.custom_tax_status === "Non-Taxable") {

        frm.set_df_property('taxes', 'hidden', 1);

        frm.set_df_property('total_taxes_and_charges', 'hidden', 1);
    } else {
        frm.set_df_property('total_taxes_and_charges', 'hidden', 0);
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
        frm.set_value('custom_tax_status', 'Non-Taxable');

        frm.clear_table('taxes');
        frm.refresh_field('taxes');
    } else {
        // خاضع (Taxable)
        frm.toggle_display('taxes', true);
        frm.set_value('custom_delivery_note_status', 'خاضع');
        frm.set_value('custom_tax_status', 'Taxable');

        if (!frm.doc.taxes || frm.doc.taxes.length === 0) {
            let row = frm.add_child('taxes');
            row.charge_type = 'On Net Total';
            row.account_head = 'VAT - YourCompany'; // Replace with your actual account
            row.rate = 14; // Adjust as needed
            frm.refresh_field('taxes');
        }
    }
}

