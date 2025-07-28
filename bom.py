from typing import Any

class KicadBomItem:
    def __init__(self, id, designator, footprint, quantity, value, supplier_info):
        self.designator:str = designator
        self.id:str = id
        self.footprint:str = footprint
        self.quantity:Any = quantity
        self.value:Any = value
        self.supplier_info:Any = supplier_info
    
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

    def get_value(self):
        return self.value


class KicadBom:
    def __init__(self):
        self.test: int = 0
        self.designator_mapping: dict[Any, Any] = None
        self.value_mapping: dict[Any, Any] = None
    
    def set_designator_mapping(self, mapping):
        self.designator_mapping = mapping

    def set_value_mapping(self, mapping):
        self.value_mapping = mapping

    def get_designator_mapping(self):
        return self.designator_mapping
    
    def get_value_mapping(self):
        return self.value_mapping

    def update_bom_item(self, designator, item:KicadBomItem):
        
        pass