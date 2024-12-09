from erpnext.stock.doctype.material_request.material_request import MaterialRequest
import frappe
from frappe.utils import (
    add_days,
    add_months,
    add_to_date,
    date_diff,
    flt,
    format_date,
    get_datetime,
    nowdate,
)

class CustomPurchaseRequest(MaterialRequest):
    def validate(self):
        self.update_purchase_request_data()

    def update_purchase_request_data(self):
        # Schedule_date (1) IN PurchaseRequest oldest_date (2) IN Delivery Note
        # (1) Total Sales Withinn 6 Months from Schedule_date (1)
        # (2) Calculate the number of months (minimum 1 month) Between 1 and 2
        schedule_date = self.schedule_date

        for item in self.items:
            item_code = item.get("item_code")
            if not item_code:
                continue

            try:
                # Fetch delivery note details for the last 6 months before the schedule_date
                sales_data = frappe.db.sql("""
                    SELECT 
                        SUM(soi.qty) AS total_qty, 
                        MIN(dn.posting_date) AS oldest_date
                    FROM 
                        `tabDelivery Note Item` soi
                    INNER JOIN 
                        `tabDelivery Note` dn ON soi.parent = dn.name
                    WHERE 
                        soi.item_code = %s
                        AND dn.posting_date BETWEEN DATE_SUB(%s, INTERVAL 6 MONTH) AND %s
                    GROUP BY soi.item_code
                """, (item_code, schedule_date, schedule_date), as_dict=True)
                print("sales",sales_data)
                if not sales_data:
                    frappe.msgprint(f"No sales data found for item: {item_code}")
                    item.custom_average_quantity_sold = 0
                    item.custom_total_quantity_sold = 0
                    item.custom_over_the_number_of_month = 0
                    continue

                total_qty = sales_data[0].get("total_qty", 0) or 0
                oldest_date = sales_data[0].get("oldest_date")

                # Calculate the number of months (minimum 1 month)
                if oldest_date:
                    months_diff = max(1, date_diff(schedule_date, oldest_date) // 30)
                else:
                    months_diff = 6

                # Compute average sold quantity
                average_qty = total_qty / 6
                rounded_qty = round(average_qty)

                # Update custom fields
                item.custom_average_quantity_sold = rounded_qty
                item.custom_total_quantity_sold = total_qty
                item.custom_over_the_number_of_month = months_diff

                # Log the values
                print(
                    f"Item: {item_code}, Rounded Avg Qty: {rounded_qty}, Total Qty: {total_qty}, Months Diff: {months_diff}"
                )

            except Exception as e:
                frappe.logger().error(f"Error updating purchase request data for item {item_code}: {e}")
                frappe.msgprint(f"Error processing item: {item_code}. Please check the logs for more details.")
