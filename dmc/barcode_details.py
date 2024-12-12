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

    # Check if barcode length is greater than or equal to 40
    if len(barcode) >= 40:
        sliced_barcode = barcode[:-4]
        gtin = sliced_barcode[2:16]
        batch_id = sliced_barcode[26:]
        raw_expiry_date = sliced_barcode[18:24]
        year = raw_expiry_date[:2]
        day = raw_expiry_date[2:4]
        month = raw_expiry_date[4:]
        formatted_date = f"{year}-{day}-{month}"

    # Check if barcode length is exactly 30
    elif len(barcode) == 30:
        gtin = barcode[2:15]  # Extract GTIN (index 2 to 15)
        batch_id = barcode[-5:]  # Extract Batch ID (last 5 characters)
        raw_expiry_date = barcode[17:23]  # Extract expiry date (index 17 to 23)
        year = raw_expiry_date[:2]
        month = raw_expiry_date[2:4]
        day = raw_expiry_date[4:]
        formatted_date = f"{year}-{month}-{day}"

    # Check if barcode length is more than 30 but less than 40
    elif 30 < len(barcode) < 40:
        gtin = barcode[2:16]  # Extract GTIN (index 2 to 16)
        batch_id = barcode[26:]  # Extract Batch ID (index 26 onwards)
        raw_expiry_date = barcode[18:24]  # Extract expiry date (index 18 to 24)
        year = raw_expiry_date[:2]
        day = raw_expiry_date[2:4]
        month = raw_expiry_date[4:]
        formatted_date = f"{year}-{day}-{month}"

    # Invalid barcode length
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





