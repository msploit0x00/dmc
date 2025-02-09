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
        return f"20{year}-{month}-{day}"

    def is_valid_date(date_str):
        if not date_str.isdigit() or len(date_str) != 6:
            return False
        try:
            month = int(date_str[2:4])
            day = int(date_str[4:6])
            return 1 <= month <= 12 and 1 <= day <= 31
        except ValueError:
            return False

    def parse_barcode(barcode_str):
        if not barcode_str.startswith('01'):
            return None

        barcode_length = len(barcode_str)
        print(f"Barcode length: {barcode_length}")

        # Special cases first
        special_cases_34 = [
            '0107323190161188102112874217241128',
            '0107323190151172102206196117250528',
            '0107323190159581102203024317250228',
            '0107323190161188102112874217241128',
            '0107323190159581102105403917240428',
            '0107323190151189102209419517250828',
            '0107323190151172102211473417251028',
            '0107323190151226102211473517251028',
            '0107323190151196102209419617250828',
            '0107323190151165102206235817250528',
            '0107323190159581102203024317250228',
            '0107323190159581102105403917240428',
            '0107323190161188102112874217241128',
            '0107323190151158102206234817250528'
        ]

        special_cases_37 = [
            '01007630006342921727041710B7196672004',
            '01007630006343221727051710B7341372004',
            '01007630006343221727050310B7274642004',
            '01007630006342921727040910B7159032004',
            '01007630006344451727070210B7544852004',
            '01007630006344451727050210B7269392004',
            '01007630006345681727070810B7561612004',
            '01007630006345681727070810B7561462004',
            '01007630006345681727061210B7453142004',
            '01007630006344141727062610B7519652004',
            '01007630007233091726073110787382001',
            '01007630007233091726073110787012001'
        ]

        # Initialize variables
        package_prefix = barcode_str[:3]
        gtin = None
        expire_prefix = None
        expire_date = None
        lot_prefix = None
        lot = None

        # Special case handling
        if barcode_str in special_cases_34:
            gtin = barcode_str[3:16]
            expire_prefix = barcode_str[26:28]
            expire_date = format_date(barcode_str[28:30], barcode_str[30:32], barcode_str[32:34])
            lot_prefix = barcode_str[16:18]
            lot = barcode_str[18:28]
        
        # Handle barcodes with 2004/2001 suffix
        elif barcode_str in special_cases_37:
            gtin = barcode_str[3:16]
            expire_prefix = barcode_str[16:18]
            expire_date = format_date(barcode_str[18:20], barcode_str[20:22], barcode_str[22:24])
            lot_prefix = barcode_str[24:26]
            # Remove the 2004/2001 suffix for lot
            lot = barcode_str[26:-4]

        # Special handling for barcodes of length 35
        elif barcode_length == 35 and barcode_str not in [
            '01007630006342921727041710B7196672004',
            '01007630006343221727051710B7341372004',
            '01007630006343221727050310B7274642004',
            '01007630006342921727040910B7159032004',
            '01007630006344451727070210B7544852004',
            '01007630006344451727050210B7269392004',
            '01007630006345681727070810B7561612004',
            '01007630006345681727070810B7561462004',
            '01007630006345681727061210B7453142004',
            '01007630006344141727062610B7519652004',
            '01007630007233091726073110787382001',
            '01007630007233091726073110787012001'
        ]:
            gtin = barcode_str[3:16]
            expire_prefix = barcode_str[16:18]
            expire_date = format_date(barcode_str[18:20], barcode_str[20:22], barcode_str[22:24])
            lot_prefix = barcode_str[24:26]
            lot = barcode_str[26:35]

        # Standard length-based parsing
        else:
            # Default GTIN parsing based on length
            if barcode_length in [34, 33, 31, 32, 36, 30]:
                gtin = barcode_str[3:16]
            elif barcode_length == 40:
                gtin = barcode_str[3:26]
            elif barcode_length == 42:
                gtin = barcode_str[3:24]
            else:
                gtin = barcode_str[3:16]

            # Default date parsing
            if barcode_length == 42:
                expire_prefix = barcode_str[24:26]
                expire_date = format_date(barcode_str[26:28], barcode_str[28:30], barcode_str[30:32])
            else:
                expire_prefix = barcode_str[16:18]
                expire_date = format_date(barcode_str[18:20], barcode_str[20:22], barcode_str[22:24])

            # Lot number parsing based on length
            lot_prefix = barcode_str[24:26] if barcode_length != 42 else barcode_str[32:34]
            
            if barcode_length == 34:
                lot = barcode_str[26:34]
            elif barcode_length == 33:
                lot = barcode_str[26:33]
            elif barcode_length == 32:
                lot = barcode_str[26:33]
            elif barcode_length == 36:
                lot = barcode_str[26:36]
            elif barcode_length == 37:
                lot = barcode_str[26:33]
            elif barcode_length == 40:
                lot = barcode_str[26:36]
            elif barcode_length == 42:
                lot = barcode_str[34:42]
            elif barcode_length == 38:
                lot = barcode_str[26:38]
            else:
                lot = barcode_str[26:34]

        # Special date overrides
        if barcode_str in ['01006153750050401726010410WI-24-2092PA', '0100615375005552172601041024-2100']:
            expire_date = '2026-04-01'
        elif barcode_str in ['01006153750050401726010310WI-24-1086PA', '0100615375005361172601031024-2072']:
            expire_date = '2026-03-01'

        # Validate prefixes
        if package_prefix not in ['010', '011', '012']:
            return None
        if expire_prefix not in ['17', '15', '11']:
            return None
        if lot_prefix not in ['10', '21']:
            return None

        return {
            "gtin": gtin,
            "batch_id": lot,
            "formatted_date": expire_date,
            "package_prefix": package_prefix,
            "expire_prefix": expire_prefix,
            "lot_prefix": lot_prefix
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
