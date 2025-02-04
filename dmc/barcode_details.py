import frappe
from dmc.get_item_code import get_item_code, get_barcode_uom, get_conversion_factor

@frappe.whitelist(allow_guest=True)
def get_barcode_details(barcode):
    if not barcode:
        return {"error": "Please pass a barcode"}

    def format_date(year, month, day):
        # Fix '00' day
        day = '01' if day == '00' else day
        # Add '20' prefix to year to make it 4 digits
        return f"20{year}-{month}-{day}"

    try:
        print(f"Processing barcode: {barcode}")  # Debug log
        
        # Remove first two digits
        barcode = barcode[2:]
        print(f"After removing first two digits: {barcode}")  # Debug log
        
        # Find first occurrence of '17' to get GTIN
        gtin_end = barcode.find('17')
        if gtin_end == -1:
            return {"error": "Invalid barcode format - missing '17' identifier"}
        
        gtin = barcode[:gtin_end]
        print(f"Found GTIN: {gtin}")  # Debug log
        
        # Move past '17' to get date
        date_start = gtin_end + 2
        raw_expiry_date = barcode[date_start:date_start + 6]
        print(f"Raw expiry date: {raw_expiry_date}")  # Debug log
        
        # Parse date components
        year = raw_expiry_date[:2]
        month = raw_expiry_date[2:4]
        day = raw_expiry_date[4:]
        formatted_date = format_date(year, month, day)
        print(f"Formatted date: {formatted_date}")  # Debug log
        
        # Find '10' after date to get batch_id
        batch_start = barcode.find('10', date_start)
        if batch_start == -1:
            return {"error": "Invalid barcode format - missing '10' identifier"}
            
        # Get batch_id (everything after '10')
        batch_id = barcode[batch_start + 2:]
        print(f"Batch ID: {batch_id}")  # Debug log

        item_code = get_item_code(barcode)
        barcode_uom = get_barcode_uom(barcode)
        conversion_factor = get_conversion_factor(item_code[0].parent, barcode_uom[0].uom)

        return {
            "gtin": gtin,
            "batch_id": batch_id,
            "formatted_date": formatted_date,
            "item_code": item_code,
            "barcode_uom": barcode_uom,
            "conversion_factor": conversion_factor
        }

    except Exception as e:
        return {"error": f"Error parsing barcode: {str(e)}"}





