
from query import Query
import argparse
import csv
from typing import Any
from bom import KicadBom, KicadBomItem
import re
from components import MULTIPLIERS
import tomllib
from headers import *
from digikey_part_handlers import API_DIGIKEY

parser = argparse.ArgumentParser(description="Arg parser for autofill BOM")

parser.add_argument("--bom",type=str, action='store', help="Path to BOM file", required=True)
parser.add_argument("--query", type=str, action='store', help="Path to Query Configurations", required=True)

kicad_bom = KicadBom()
query = Query()

PREDICTIONS_OUTPUT = "predictions_output.txt"

def update_bom(query_config):

    with open(query_config, "rb") as qconfig:
        config = tomllib.load(qconfig)
    
    queries = config["query"]["queries"]

    print("Running queries...")

    for _query in queries:

        query_content = config[_query]

        designators = query_content["designator"][0].split(',')
        query_text = query_content["query"]

        rows, indices, distances = query.do_query(query_text, designators[0], True)

        for designator in designators:
            update_part_kidcad(designator, 0)
        
        with open(PREDICTIONS_OUTPUT, 'a') as f:
            current_rows = query.get_current_rows()
            
            f.write(f"{(' ').join(designators)}\n")
            f.write(f"Query {query_text}\n")
            f.write(f"Predictions\n")

            for row in current_rows:
                f.write(f"{row}\n")

            f.write("Distances \n")
            f.write(f"{str(distances)}\n")
            f.write("\n\n")

    test_export_bom(kicad_bom.build_bom_list_for_csv())

def normalize_bom_value(item):

    item_norm = item.upper()

    # Replace special symbols such as µ 
    item_norm = item_norm.replace("µ", "U")

    re_match = re.match(r"^([0-9.]+)\s*([A-Z]*)$", item_norm, re.IGNORECASE)

    if re_match:
        number, unit = re_match.groups()
        if unit:
            normalized_value = MULTIPLIERS[unit] * float(number)
            return normalized_value
    return item


def bom_items_equal(bom_item:KicadBomItem, bom_items:KicadBomItem):
    
    same = True
    for item in bom_items:
        same = bom_item.is_equal(item)

    return same
    
def test_export_bom(bom_contents):
    with open("test_output_bom.csv",'w') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
        csv_writer.writerows(bom_contents)

def handle_kicad_bom(bom):

    print("Handling kicad bom")
    designator_mapping = {}
    value_mapping: dict[Any, list[Any]] = {}

    with open(bom, newline='', encoding='utf-8') as bom_csv:

        reader = csv.DictReader(bom_csv, delimiter=';')

        for row in reader:
            designators = row["Designator"].split(",")
            
            footprint = row["Footprint"]
            quantity = row["Quantity"]
            value = row["Designation"]
            sup_info = row["Supplier and ref"]
            id = row["Id"]

            normalized_value = normalize_bom_value(value)

            # Need to normalize the value
            # For a resistor, the value could be 100k, 100K, 100kOhm

            for designator in designators:
                bom_item = KicadBomItem(id, designator, footprint, quantity,
                                        value, sup_info)
                
                designator_mapping[designator] = bom_item

                try:
                    value_mapping[normalized_value].append(bom_item)
                except KeyError:
                    value_mapping[normalized_value] = []
                    value_mapping[normalized_value].append(bom_item)    

    kicad_bom.set_designator_mapping(designator_mapping)
    kicad_bom.set_value_mapping(value_mapping)

def update_part_kidcad(designator, index):
    
    if query.get_api() == API_DIGIKEY:
        
        content = query.get_current_rows()


        if index <= len(content):
            
            item = content[index]
            
            kicad_bom_item = kicad_bom.get_designator_mapping()[designator]
            old_value = kicad_bom_item.get_value()
            new_value = item.get(HEADER_VALUE)
            supplier_info = API_DIGIKEY + "-" + item.get(HEADER_PRODUCT_NUM)
            tolerance = item.get(HEADER_TOLERANCE)
            voltage_rating = item.get(HEADER_VR)
            product_url = item.get(HEADER_URL)
            datasheet_url = item.get(HEADER_DATASHEET_URL)
            footprint = item.get(HEADER_FOOTPRINT)
            normalized_value = normalize_bom_value(new_value)

            if kicad_bom_item:
                kicad_bom_item.set_value(new_value)
                kicad_bom_item.set_supplier_info(supplier_info)
                kicad_bom_item.set_tolerance(tolerance)
                kicad_bom_item.set_voltage_rating(voltage_rating)
                kicad_bom_item.set_product_url(product_url)
                kicad_bom_item.set_datasheet_url(datasheet_url)
                kicad_bom_item.set_footprint(footprint)

            bom_item = kicad_bom.get_value_mapping().get(normalize_bom_value(old_value))

            if bom_item:
                # bom_item.remove(kicad_bom_item)
                bom_item_new = kicad_bom.get_value_mapping().get(normalized_value)

                if bom_item_new and bom_items_equal(kicad_bom_item, bom_item_new):
                    bom_item_new.append(kicad_bom_item)
                else:
                    kicad_bom.get_value_mapping()[normalized_value] = []
                    kicad_bom.get_value_mapping()[normalized_value].append(kicad_bom_item)

def main():
    args = parser.parse_args()

    query.initialize_parts_query_engine(True)

    with open (PREDICTIONS_OUTPUT, "w") as f:
        pass

    handle_kicad_bom(args.bom)
    update_bom(args.query)

if __name__ == "__main__":
    main()