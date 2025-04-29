frappe.provide('erpnext');

class CustomSerialNoBatchSelector extends erpnext.SerialNoBatchSelector {
    constructor(opts) {
        super(opts);
    }

    get_attach_field() {
        console.log('Overriding get_attach_field');
    
        let fields = super.get_attach_field();
    
        // Find the field you want to override
        let field = fields.find(f => f.fieldname === 'omar_hany');
    
        if (field) {
            // Override existing field properties
            field.label = 'Manga1232';
            field.description = 'Custom field added by Omar Hany';
            field.onchange = () => console.log('omar_hany field changed');
        } else {
            console.warn('Field omar_hany not found!');
        }
    
        return fields;
    }
}

frappe.after_ajax(() => {
    console.log('Overriding erpnext.SerialNoBatchSelector now...');
    erpnext.SerialNoBatchSelector = CustomSerialNoBatchSelector;
});
