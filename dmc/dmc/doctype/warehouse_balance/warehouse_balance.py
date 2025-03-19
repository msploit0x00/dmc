import frappe
from frappe.model.document import Document

class WarehouseBalance(Document):
    @frappe.whitelist()
    def get_stock_data(self):
      
        self.set("items", [])

     
        filters = {
            "posting_date": ["between", [self.from_date, self.to_date]],
        }
        if self.warehouse:
            filters["warehouse"] = self.warehouse
        if self.item:
            filters["item_code"] = self.item
        if self.item_group:
            item_codes = frappe.get_all("Item", filters={"item_group": self.item_group}, pluck="name")
            filters["item_code"] = ["in", item_codes]


        stock_entries = frappe.get_all("Stock Ledger Entry",
            filters=filters,
            fields=["item_code", "warehouse", "actual_qty"]
        )

        frappe.msgprint(f"Found {len(stock_entries)} Stock Ledger Entries")  
        frappe.log_error("Stock Ledger Data", stock_entries)

        total_balance_qty = 0

        for entry in stock_entries:
            
            item_doc = frappe.get_doc("Item", entry["item_code"])

            new_item = {
                "item": entry["item_code"],
                "warehouse": entry["warehouse"],
                "qty_change": entry["actual_qty"],
                "item_name": item_doc.item_name,
                "item_group": item_doc.item_group,
            }
            
            frappe.msgprint(f"Adding Item: {new_item}") 
            self.append("items", new_item)

            total_balance_qty += entry["actual_qty"]

        
        self.total_balance_quantity = total_balance_qty

        
        self.save()
        frappe.msgprint("Stock data added. Refreshing form...")
        
        return True
