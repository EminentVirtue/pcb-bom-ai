from typing import Any
from components import DEFAULT_CONFIG_FILE
import tomllib

class KicadBomItem:
    def __init__(self, id, designator, footprint, quantity, value, supplier_info):
        self.designator:str = designator
        self.id:str = id
        self.footprint:str = footprint
        self.quantity:str = quantity
        self.value:str = value
        self.supplier_info:str = supplier_info
        self.tolerance:str = ""
        self.voltage_rating:str = ""
        self.product_url:str = ""
        self.datasheet_url:str = ""
    
    def set_designator(self, d):
        self.designator = d
    
    def set_id(self, id):
        self.id = id
    
    def set_footprint(self, fp):
        self.footprint = fp

    def set_quantity(self, q):
        self.quantity = q

    def set_value(self, val):
        self.value = val
    
    def set_supplier_info(self, sp):
        self.supplier_info = sp

    def set_tolerance(self, tol):
        self.tolerance = tol
    
    def set_voltage_rating(self, rating):
        self.voltage_rating = rating

    def set_product_url(self, url):
        self.product_url = url
    
    def set_datasheet_url(self, url):
        self.datasheet_url = url

    def get_datasheet_url(self):
        return self.datasheet_url

    def get_product_url(self):
        return self.product_url
    
    def get_tolerance(self):
        return self.tolerance
    
    def get_voltage_rating(self):
        return self.voltage_rating
    
    def get_value(self):
        return self.value
    
    def get_footprint(self):
        return self.footprint
    
    def get_supplier_info(self):
        return self.supplier_info
    
    def get_designator(self):
        return self.designator
    
    def is_equal(self, item2):
        footprint_same = self.get_footprint() == item2.get_footprint()
        value_same = self.get_value() == item2.get_value()
        supplier_same = self.get_supplier_info() == item2.get_supplier_info()

        return footprint_same and value_same and supplier_same

"""
With Kicad BOMS, the designators are lumbed together based on their value
For example, if we had C1,C2,C3 all as 10 uF, then when the BOM is exported
"""
class KicadBom:
    def __init__(self):
        self.test: int = 0
        self.designator_mapping: dict[Any, Any] = None
        self.value_mapping: dict[Any, Any] = None
        self.default_configs = self.init_default_configs()

    def set_designator_mapping(self, mapping):
        self.designator_mapping = mapping

    def init_default_configs(self):
        with open(DEFAULT_CONFIG_FILE, "rb") as config:
            config =  tomllib.load(config)

        return config

    def set_value_mapping(self, mapping):
        self.value_mapping = mapping

    def get_designator_mapping(self):
        return self.designator_mapping
    
    def get_value_mapping(self):
        return self.value_mapping

    def update_bom_item(self, designator, item:KicadBomItem):
        pass

    def build_bom_list_for_csv(self):
        csv_content = []
        bom_headers = self.default_configs["bom-headers"]["kicad"]

        csv_content.append(bom_headers)
        values_mapping = self.value_mapping
        values = values_mapping.keys()
        i = 1

        for value in values:

            bom_items = values_mapping.get(value)

            if bom_items:
                designators = []
                reference_item = bom_items[0]

                for bom_item in bom_items:
                    designators.append(bom_item.get_designator())

                content = [
                    str(i),
                    (",").join(designators),
                    reference_item.get_footprint(),
                    str(len(designators)),
                    reference_item.get_value(),
                    reference_item.get_supplier_info(),
                    reference_item.get_tolerance(),
                    reference_item.get_voltage_rating(),
                    reference_item.get_product_url(),
                    reference_item.get_datasheet_url()
                ]

                csv_content.append(content)

            i = i + 1
                    
        return csv_content
                    
