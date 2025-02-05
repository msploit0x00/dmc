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
    if len(barcode) >= 40 or len(barcode) == 37:
        sliced_barcode = barcode[:-4]  # Remove last 4 digits
        # Find positions of markers
        seventeen_pos = sliced_barcode.find('17')
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
        seventeen_pos = barcode.find('17')
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