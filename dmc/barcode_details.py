import frappe


from dmc.get_item_code import get_item_code
from dmc.get_item_code import get_barcode_uom
from dmc.get_item_code import get_conversion_factor



@frappe.whitelist(allow_guest=True)
def get_barcode_details(barcode):
    if not barcode:
        return {"error": "Please pass a barcode"}

    gtin = ""
    batch_id = ""
    formatted_date = ""
    item_code = get_item_code(barcode)
    barcode_uom = get_barcode_uom(barcode)
    conversion_factor = get_conversion_factor(item_code[0].parent,barcode_uom[0].uom)

    def format_date(year, month, day):
        # Fix '00' day
        day = '01' if day == '00' else day
        return f"{year}-{month}-{day}"

    def find_valid_date_marker(barcode_str):
        # Find all occurrences of '17'
        pos = -1
        while True:
            pos = barcode_str.find('17', pos + 1)
            if pos == -1:  # No more '17' found
                break
            # Check if followed by 6 digits
            if len(barcode_str) >= pos + 8:  # Need 8 chars: '17' + 6 digits
                date_part = barcode_str[pos+2:pos+8]
                if date_part.isdigit():
                    # Basic date validation
                    month = int(date_part[2:4])
                    day = int(date_part[4:6])
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        return pos
        return -1

    # Check if barcode length is greater than or equal to 40
    if len(barcode) >= 40 or len(barcode) == 37:
        sliced_barcode = barcode[:-4]  # Remove last 4 digits
        # Find positions of markers
        seventeen_pos = find_valid_date_marker(sliced_barcode)
        if seventeen_pos == -1:
            return {"error": "Invalid date format in barcode"}
        
        ten_pos = sliced_barcode.find('10', seventeen_pos)
        
        gtin = sliced_barcode[2:seventeen_pos]
        raw_expiry_date = sliced_barcode[seventeen_pos+2:ten_pos]  # Skip the '17'
        batch_id = sliced_barcode[ten_pos+2:]  # Skip the '10'
        
        year = raw_expiry_date[:2]
        month = raw_expiry_date[2:4]
        day = raw_expiry_date[4:]
        formatted_date = format_date(year, month, day)
    
    # For all other barcodes (30-36 digits)
    elif len(barcode) >= 30:
        # Find positions of markers
        seventeen_pos = find_valid_date_marker(barcode)
        if seventeen_pos == -1:
            return {"error": "Invalid date format in barcode"}
            
        ten_pos = barcode.find('10', seventeen_pos)
        
        gtin = barcode[2:seventeen_pos]
        raw_expiry_date = barcode[seventeen_pos+2:ten_pos]  # Skip the '17'
        batch_id = barcode[ten_pos+2:]  # Skip the '10'
        
        year = raw_expiry_date[:2]
        month = raw_expiry_date[2:4]
        day = raw_expiry_date[4:]
        formatted_date = format_date(year, month, day)

    # Invalid length
    else:
        return {"error": "Invalid barcode length"}

    # Return the parsed details
    return {
        "gtin": gtin,
        "batch_id": batch_id,
        "formatted_date": formatted_date,
        "item_code": item_code,
        "barcode_uom": barcode_uom,
        "conversion_factor": conversion_factor
    }
