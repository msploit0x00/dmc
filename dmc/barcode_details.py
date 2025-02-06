import frappe


from dmc.get_item_code import get_item_code
from dmc.get_item_code import get_barcode_uom
from dmc.get_item_code import get_conversion_factor



@frappe.whitelist(allow_guest=True)
def get_barcode_details(barcode):
    if not barcode:
        return {"error": "Please pass a barcode"}

    def format_date(year, month, day):
        # Fix '00' day
        day = '01' if day == '00' else day
        return f"20{year}-{month}-{day}"  # Added '20' prefix for year

    def is_valid_date(date_str):
        if not date_str.isdigit() or len(date_str) != 6:
            return False
        try:
            month = int(date_str[2:4])
            day = int(date_str[4:6])
            return 1 <= month <= 12 and 1 <= day <= 31
        except ValueError:
            return False

    def find_valid_date_marker(barcode_str, start_pos):
        pos = start_pos
        while True:
            pos = barcode_str.find('17', pos)
            if pos == -1:  # No more '17' found
                return -1
            # Check if followed by valid date
            if len(barcode_str) >= pos + 8:  # Need 8 chars: '17' + 6 digits
                date_part = barcode_str[pos+2:pos+8]
                if is_valid_date(date_part):
                    # Found valid date marker
                    return pos
            pos += 2  # Move past current '17'
        return -1

    def find_batch_marker(barcode_str, after_pos):
        batch_pos = barcode_str.find('10', after_pos)
        if batch_pos == -1:
            return -1
        # Optional: Add any validation for what should follow '10'
        # For example, minimum length, allowed characters, etc.
        return batch_pos

    def parse_barcode(barcode_str):
        if not barcode_str.startswith('01'):
            return None
            
        # Find the valid date marker '17' after the '01' prefix
        gtin_start = 2
        date_pos = find_valid_date_marker(barcode_str, gtin_start)
        if date_pos == -1:
            return None
            
        # GTIN is everything between '01' and '17'
        gtin = barcode_str[gtin_start:date_pos]
        
        # Extract date (6 digits after '17')
        date_start = date_pos + 2
        date_end = date_start + 6
        if len(barcode_str) < date_end:
            return None
            
        raw_date = barcode_str[date_start:date_end]
            
        # Look for batch marker '10' after date
        batch_pos = find_batch_marker(barcode_str, date_end)
        if batch_pos == -1:
            return None
            
        # Extract batch (everything after '10')
        batch_start = batch_pos + 2
        batch_id = barcode_str[batch_start:]
        
        # Format date
        year = raw_date[:2]
        month = raw_date[2:4]
        day = raw_date[4:]
        formatted_date = format_date(year, month, day)
        
        return {
            "gtin": gtin,
            "batch_id": batch_id,
            "formatted_date": formatted_date
        }

    # Parse the barcode
    result = parse_barcode(barcode)
    if not result:
        return {"error": "Invalid barcode format"}

    # Get additional details
    item_code = get_item_code(barcode)
    barcode_uom = get_barcode_uom(barcode)
    conversion_factor = get_conversion_factor(item_code[0].parent, barcode_uom[0].uom)

    # Add additional details to result
    result.update({
        "item_code": item_code,
        "barcode_uom": barcode_uom,
        "conversion_factor": conversion_factor
    })

    return result
