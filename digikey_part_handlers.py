from typing import Any
from components import *
from headers import *

"""
The idea of this file is to provide handlers to parsing the pertinent data of
each component we're interested in

If the handler for a particular part needs to be changed, then all that must be done
is change it in this file and update the handler in the toml
"""

FIELD_MANUFACTURER = "manufacturer"
FIELD_PRODUCT_STATUS = "product_status"
FIELD_PRODUCT_VARIATIONS = "product_variations"
FIELD_STANDARD_PRICING = "standard_pricing"
FIELD_QUANTITY_AVAILABLE = "quantity_available"
FIELD_MANUFACTURER_PN = "manufacturer_product_number"
FIELD_DK_URL = "product_url"
FIELD_CAPACITANCE = "Capacitance"
FIELD_RESISTANCE = "Resistance"

FIELD_TAPE_REEL = "Tape & Reel (TR)"
FIELD_CUT_TAPE = "Cut Tape (CT)"
FIELD_DIGIREEL = "Digi-Reel®"

PRICES_QUERY_POS = 0
PRICES_DB_POS = 1

DIGIKEY_FIELD_TO_HEADER = {
    FIELD_MANUFACTURER: HEADER_MANUFACTURER,
    FIELD_STANDARD_PRICING: HEADER_STANDARD_PRICING,
    FIELD_QUANTITY_AVAILABLE: HEADER_QUANTITY,
    FIELD_DK_URL: HEADER_URL,
    FIELD_MANUFACTURER_PN: HEADER_PRODUCT_NUM,
    FIELD_CAPACITANCE : HEADER_VALUE,
    FIELD_RESISTANCE: HEADER_VALUE
}

# For parameters having a nested map as the value
def handle_special_field(product, field):
    
    ret_content = None
    prices = False

    if field == FIELD_MANUFACTURER:
        manuf_mapping = product[FIELD_MANUFACTURER]
        manuf_name = manuf_mapping["name"]

        if manuf_name is not None:
            ret_content = manuf_name
        
    if field == FIELD_PRODUCT_STATUS:
        status = product[FIELD_PRODUCT_STATUS]["status"]
        ret_content = status
    
    if field == FIELD_STANDARD_PRICING:
        # standard_pricing = product[FIELD_PRODUCT_VARIATIONS][0][FIELD_STANDARD_PRICING]
        standard_pricings = product[FIELD_PRODUCT_VARIATIONS]
        prices_query = []
        prices_plain = []
        prices_db = []
        
        for pricing in standard_pricings:

            standard_pricing = pricing["standard_pricing"]
            name = pricing["package_type"]["name"]
            prices_plain = []

            for sp in standard_pricing:
                break_quantity = sp["break_quantity"]
                total_price = sp["total_price"]
                prices_query.append(str(break_quantity) +  f" in {name} for {total_price} ")
                prices_plain.append(str(break_quantity) + f" for {total_price}")

            prices_db.append((" ").join(prices_plain))

        ret_content = [(" ").join(prices_query), prices_db]
        prices = True
    
    return [prices, ret_content]
       

def generic_component_handler(component:int,products: Any, configs: Any):
    fields = configs[COMPONENT_TOML_MAPPING_ID[component]]["fields"]
    common_fields = configs["fields_common"]["fields"]
    common_fields_special = configs["fields_common"]["special_fields"]

    cfields_len = len(common_fields)
    cfields_special_len = len(common_fields_special)
    num = max(cfields_special_len, cfields_len)

    entry = []
    headers = []
    pricing = [[FIELD_TAPE_REEL, FIELD_CUT_TAPE, FIELD_DIGIREEL]]
    
    if fields is None:
        return entry 
    
    for i in range(num):
        
        if i < cfields_len:
            headers.append(common_fields[i])
        if i < cfields_special_len:
            headers.append(common_fields_special[i])

    entry.append(headers + fields)

    for product in products:

        product_dict = product.to_dict()
        parameters = product_dict["parameters"]
        row = []    

        # Handle common fields
        for i in range(num):
            
            if i < cfields_len:
                row.append(str(product_dict[common_fields[i]]))
            if i < cfields_special_len:
                prices, data = handle_special_field(product_dict, common_fields_special[i])

                if data and prices:
                    row.append(str(data[PRICES_QUERY_POS]))
                    pricing.append(data[PRICES_DB_POS])
                else:
                    row.append(str(data))
    
    
        # Handle component specific fields
        for field in fields:
            field_data = next((p['value_text'] for p in parameters if p['parameter_text'] == field), None)
            row.append(field_data)

        entry.append(row)

    return [entry, pricing]


def dk_rhandler(data:Any, configs: Any):
    return generic_component_handler(component=COMPONENT_RESISTOR, products=data, configs=configs)
        
def dk_chandler(data:Any, configs:Any):
    return generic_component_handler(component=COMPONENT_CAPACITOR, products=data, configs=configs)

def dk_ihandler(data:Any, configs:Any):
    return generic_component_handler(component=COMPONENT_INDUCTOR, products=data, configs=configs)

