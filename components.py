import tomllib
from typing import Any

COMPONENT_RESISTOR = 0x00
COMPONENT_CAPACITOR = 0x01
COMPONENT_INDUCTOR = 0x02
COMPONENT_CRYSTAL = 0x03
COMPONENT_CONNECTOR = 0x04
COMPONENT_REGULATOR = 0x05
COMPONENT_FLASH = 0x06
COMPONENT_CONNECTOR = 0x07

DEFAULT_CONFIG_FILE = "default_config.toml"
API_DIGIKEY = "Digikey"

# Map the component IDs to the toml entries
# TODO perhaps this should be supplied by a file

COMPONENT_TOML_MAPPING_ID = {
    COMPONENT_RESISTOR: "resistor",
    COMPONENT_CAPACITOR: "capacitor",
    COMPONENT_INDUCTOR: "inductor",
    COMPONENT_CRYSTAL: "crystal",
    COMPONENT_CONNECTOR: "connector",
    COMPONENT_REGULATOR: "regulator",
    COMPONENT_FLASH: "flash-memory"

    # ... etc
}

COMPONENT_TOML_MAPPING_NAME = {
   "resistor": COMPONENT_RESISTOR,
   "capacitor": COMPONENT_CAPACITOR,
   "inductor": COMPONENT_INDUCTOR,  
   "crystal": COMPONENT_CRYSTAL,
   "connector": COMPONENT_CONNECTOR,
   "regulator": COMPONENT_REGULATOR,
   "flash-memory": COMPONENT_FLASH
}

COMPONENT_SPECIFIC = [
    "Flash",
    "Regulator",
    "Connector"
]
COMPONENT_SPECIFIC_NAME = [
    "flash-memory",
    "regulator",
    "connector"
]

COMPONENT_ANY = "any"

MULTIPLIERS = {
    "": 1,
    "R": 1,
    "OHM": 1,
    "OHMS": 1,
    "K": 1e3,
    "KOHM": 1e3,
    "KOHMS": 1e3,
    "M": 1e6,
    "MOHM": 1e6,
    "MOHMS": 1e6,
    "P": 1e-12,
    "PF": 1e-12,
    "N": 1e-9,
    "NF": 1e-9,
    "U": 1e-6,
    "UF": 1e-6,
    "MF": 1E-6,
    "F": 1,
    "HZ" : 1,
    "KHZ": 1e3,
    "MHZ": 1e6,
    "GHZ": 1e9,
    "MBIT":1e6,
    "V": 1,
    "MV": 1e-3
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
