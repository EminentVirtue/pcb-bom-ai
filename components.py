import tomllib
from typing import Any

COMPONENT_RESISTOR = 0x00
COMPONENT_CAPACITOR = 0x01
COMPONENT_INDUCTOR = 0x02

DEFAULT_CONFIG_FILE = "default_config.toml"
API_DIGIKEY = "digikey"

# Map the component IDs to the toml entries
# TODO perhaps this should be supplied by a file

COMPONENT_TOML_MAPPING_ID = {
    COMPONENT_RESISTOR: "resistor",
    COMPONENT_CAPACITOR: "capacitor",
    COMPONENT_INDUCTOR: "inductor"

    # ... etc
}

COMPONENT_TOML_MAPPING_NAME = {
   "resistor": COMPONENT_RESISTOR,
   "capacitor": COMPONENT_CAPACITOR,
   "inductor": COMPONENT_INDUCTOR
}


API_SUCCESS = 1
API_FAILURE = 0

BOM_FORMAT_KICAD = 0x0

default_configs = None

def get_api_databases(api):

    if api == API_DIGIKEY:
        return default_configs["digikey-databases"]

def get_database_for_component(configs, component):
    databases = configs["digikey-databases"]
    return databases[component]
