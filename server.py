from flask import *
import os
from query import Query
from components import BOM_FORMAT_KICAD, API_DIGIKEY
import csv
from bom import KicadBomItem, KicadBom
from typing import Any
from headers import *

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

@app.route('/update-bom', methods = ['POST'])
def update_part():
    designator = request.args.get('des')
    index = request.args.get('index')

    

    pass


@app.route('/request-query')
def request_from_query():
    query_content = request.args.get('content')
    response = query.do_query(query_content)
    return jsonify(response)

@app.route("/update-qengine")
def update_component_engine():
    print("Initializing parts query engine")
    query.initialize_parts_query_engine()
    return jsonify({'message': 'Updated component engine!'})


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

                        collision_box_metadata.append({
                            "name": comp["REF"],
                            "x": pos[0],
                            "y": pos[1],
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

def update_part_kidcad(designator, index):
    
    if query.get_api() == API_DIGIKEY:
        
        content = query.get_current_rows()

        if index <= len(content):
            
            item = content[index]
            kicad_bom_item = kicad_bom.get_designator_mapping()[designator]
            old_value = kicad_bom_item.get_value()

            if kicad_bom_item:
                kicad_bom_item.set_value(item[HEADER_VALUE])
                kicad_bom_item.set_supplier_info(item[HEADER_URL])

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

            for designator in designators:
                bom_item = KicadBomItem(id, designator, footprint, quantity,
                                        value, sup_info)
                
                designator_mapping[designator] = bom_item

                try:
                    value_mapping[value].append(bom_item)
                except KeyError:
                    value_mapping[value] = []
                    value_mapping[value].append(bom_item)    

        kicad_bom.set_designator_mapping(designator_mapping)
        kicad_bom.set_value_mapping(value_mapping)



def handle_bom_file(bom):

    if query.bom_format == BOM_FORMAT_KICAD:
        handle_kicad_bom(bom)

    return jsonify({'message': 'successfully handled bom'})



if __name__ == '__main__':
    app.run(debug =True)