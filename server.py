from flask import *
import os
from query import Query
from components import BOM_FORMAT_KICAD, API_DIGIKEY, MULTIPLIERS
import csv
from bom import KicadBomItem, KicadBom
from typing import Any
from headers import *
import re

app = Flask(__name__)
UPLOAD_PATH = 'uploads'
os.makedirs(UPLOAD_PATH, exist_ok=True)

designator_mapping = {}
bom_mapping = {}

# The most common package sizes for lumped components (resistors, capacitors, inductors)

# TODO add an exhaustive list of packages
# Also, these would obviously best be kept in an external file
# that we would read on app initialization. For the POC, we'll
# just add the footprints for the board we're demoing with
PACKAGE_0402 = "0402"
PACKAGE_0603 = "0603"
PACKAGE_0805 = "0805"
PACKAGE_SOT223 = "SOT-223"
PACKAGE_SOIC8 = "SOIC-8"
PACKAGE_PINHEADER = "PinHeader"
PACKAGE_CRYSTAL = "Crystal"

PINHEADER_PINCOUNT_REGEX = r'(\d+)x(\d+)'
PINHEADER_ORIENTATION_REGEX = r'(Vertical|Horizontal)'
PACKAGE_PITCH_REGEX = r'P([0-9.]+)mm'
PACKAGE_CRYSTAL_REGEX = r'([0-9.]+)x([0-9.])+mm'

PINHEADER_VERTICAL = "Vertical"
PINHEADER_HORIZONTAL = "Horizontal"

query = Query()
kicad_bom = KicadBom()

TEST_COMPONENT_LIST = [
    {
        "value" : "2.7 kohm",
        "qty" : 5,
        "cost" : "$0.020",
        "footprint" : PACKAGE_0402,
        "rating": "0.10W"
    },
    {
        "value" : "2.7 kohm",
        "qty" : 5,
        "cost" : "$0.020",
        "footprint" : PACKAGE_0402,
        "rating": "0.10W"
    },
    {
        "value" : "2.7 kohm",
        "qty" : 5,
        "cost" : "$0.020",
        "footprint" : PACKAGE_0402,
        "rating": "0.10W"
    }
]

# Try to relate the footprint to a width/height to use for collision detection
def footprint_to_dimensions(package):
    width = 0
    height = 0

    # First check most common packages
    if PACKAGE_0402 in package:
        width = 1.0
        height = 0.5
    elif PACKAGE_0603 in package:
        width = 1.6
        height = 0.8
    elif PACKAGE_0805 in package:
        width = 2.0
        height = 1.25
    elif PACKAGE_SOT223 in package:
        width = 6.50
        height = 6.70
    elif PACKAGE_SOIC8 in package:
        width = 3.9
        height = 4.9
    elif PACKAGE_PINHEADER in package:
        re_match = re.search(PINHEADER_PINCOUNT_REGEX, package)

        if re_match:
            rows = int(re_match.group(1))
            cols = int(re_match.group(2))

        re_match = re.search(PACKAGE_PITCH_REGEX, package)
        if re_match:
            pitch_mm = float(re_match.group(1))

        width = rows * pitch_mm
        height = cols * pitch_mm
        
        re_match = re.search(PINHEADER_ORIENTATION_REGEX, package, re.IGNORECASE)
        if re_match:
            orientation = re_match.group(1)

            if orientation == PINHEADER_VERTICAL:
                temp = width
                width = height
                height = temp
            
    elif PACKAGE_CRYSTAL in package:
        re_match = re.search(PACKAGE_CRYSTAL_REGEX, package)

        if re_match:
            width = re_match.group(1)
            height = re_match.group(2)
    else:
        # Attempt to decipher the dimensions
        pass


    """
    TODO for components that don't fit a specific criteria, we could use ML
    to match a package to its best fit. For example, a package 'USB-B...' may
    not explicitly mention the dimensions, but all USB-B connectors are standard
    so we can match this package to a standard
    """

    return [width, height]

# Update parts catalogue by doing an API query
def update_query_catalogue():
    pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test', methods=['POST'])
def test():
    return jsonify({'message': 'test response'})

@app.route('/request-parts')
def get_parts():
    cname = request.args.get('name')
    content = query.do_designator_query(cname)
    return jsonify(content)

@app.route('/update-bom')
def update_part():
    designator = request.args.get('des')
    index = request.args.get('index')
    update_part_kidcad(designator, int(index))

    return jsonify({'message': 'Updated BOM item'})

@app.route('/request-query')
def request_from_query():
    query_content = request.args.get('content')
    query_designator = request.args.get('des')
    results, indices, flat_distances = query.do_query(query_content, query_designator)
    return jsonify(results)

@app.route("/update-qengine")
def update_component_engine():
    print("Initializing parts query engine")
    query.initialize_parts_query_engine()
    return jsonify({'message': 'Updated component engine!'})

@app.route('/download-bom')
def download_bom():
    test_export_bom(kicad_bom.build_bom_list_for_csv())
    path = os.path.join(app.root_path, "databases")
    return send_from_directory(path, 'user_bom.csv')

@app.route('/export-bom')
def export_current_bom():
    return jsonify({'message': 'Export successful'})

def test_export_bom(bom_contents):
    path = os.path.join(app.root_path, "databases", "user_bom.csv")
    with open(path,'w') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
        csv_writer.writerows(bom_contents)

@app.route('/upload', methods=['POST'])
def handle_files():
    
    file = request.files['file']
    filepath = os.path.join(UPLOAD_PATH, file.filename)
    file.save(filepath)

    collision_box_metadata = []

    if ".pos" in file.filename:
        try:
            with open(file=filepath) as f:
                for line in f:
                    items = line.split()

                    if "#" in items[0]:
                        continue
                    else:
                        pos = (items[3], items[4])
                        designator_mapping[pos] = {"REF":  items[0], "VALUE" : items[1], 
                                                                    "PACKAGE" : items[2], "ROT": items[5]}
                        
                        comp = designator_mapping[pos]
                        height, width = footprint_to_dimensions(comp["PACKAGE"])
                        
                        x = pos[0]
                        y = pos[1]
                        
                        if PACKAGE_PINHEADER in comp["PACKAGE"] and int(float(comp["ROT"])) == 0:
                            x_pos = float(x)
                            y_pos = float(y)

                            collision_box_metadata.append({
                                "name": comp["REF"],
                                "x": x_pos + ((width / 2) if x_pos < 0 else 0),
                                "y": y_pos - (height / 2),
                                "z": 0,
                                "width": width,
                                "height" : height,
                                "depth" : 0.5
                            })

                        else:
                            collision_box_metadata.append({
                                "name": comp["REF"],
                                "x": x,
                                "y": y,
                                "z": 0,
                                "width": width,
                                "height" : height,
                                "depth" : 0.5
                            })

            return jsonify(collision_box_metadata)
                        
        except FileNotFoundError:
            pass
    elif ".csv" in file.filename:
        return handle_bom_file(filepath)

"""
Since we're using a value to bom item mapping, the values
need to be normalized. The BOM may have a value as 100k, but the
API may have the value as 100 kOhm
"""
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

    # test_export_bom(kicad_bom.build_bom_list_for_csv())

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

def handle_bom_file(bom):

    if query.bom_format == BOM_FORMAT_KICAD:
        handle_kicad_bom(bom)

    return jsonify({'message': 'successfully handled bom'})



if __name__ == '__main__':
    app.run(debug =True)