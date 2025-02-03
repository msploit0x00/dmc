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

    # Check if barcode length is greater than or equal to 40
    if len(barcode) >= 40:
        sliced_barcode = barcode[:-4]
        gtin = sliced_barcode[2:16]
        batch_id = sliced_barcode[26:]
        raw_expiry_date = sliced_barcode[18:24]
        year = raw_expiry_date[:2]
        month = raw_expiry_date[4:]
        day = raw_expiry_date[2:4]
        formatted_date = format_date(year, month, day)

    # For exactly 37-digit barcodes
    elif len(barcode) == 37:
        sliced_barcode = barcode[:-4]
        gtin = sliced_barcode[2:16]
        batch_id = sliced_barcode[26:]
        raw_expiry_date = sliced_barcode[18:24]
        year = raw_expiry_date[:2]
        month = raw_expiry_date[2:4]
        day = raw_expiry_date[4:]
        formatted_date = format_date(year, month, day)

    # For exactly 30-digit barcodes
    elif len(barcode) == 30:
        gtin = barcode[2:15]  # Extract GTIN (index 2 to 11)
        batch_id = barcode[-5:]  # Extract Batch ID (last 5 characters)
        raw_expiry_date = barcode[17:23]  # Extract expiry date
        year = raw_expiry_date[:2]
        month = raw_expiry_date[2:4]
        day = raw_expiry_date[4:]
        formatted_date = format_date(year, month, day)

    # For barcodes between 31-36 digits
    elif 30 < len(barcode) < 37:
        gtin = barcode[2:16]
        
        # Try different date positions based on barcode format
        if barcode[17] == '2':  # Check position 17 first for year starting with 2
            raw_expiry_date = barcode[17:23]
            batch_id = barcode[23:]
        elif barcode[18] == '2':  # Then check position 18
            raw_expiry_date = barcode[18:24]
            batch_id = barcode[24:]
        else:  # Default case
            raw_expiry_date = barcode[16:22]
            batch_id = barcode[22:]
            
        year = raw_expiry_date[:2]
        month = raw_expiry_date[2:4]
        day = raw_expiry_date[4:]
        formatted_date = format_date(year, month, day)

    # For barcodes between 38-39 digits
    elif 37 < len(barcode) < 40:
        gtin = barcode[2:16]
        batch_id = barcode[26:]
        raw_expiry_date = barcode[18:24]
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




