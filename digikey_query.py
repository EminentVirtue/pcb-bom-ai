"""
    digikey_query.py 

    This python file shows making search query items for the notorious
    vendor Digikey. Interfaces with digikey API, whose source code can
    be found here https://github.com/peeter123/digikey-api

"""


import os
from pathlib import Path
import tomllib
import csv
import importlib

import digikey
from digikey.v4.productinformation import KeywordRequest
from components import *
import logging

DIGIKEY_CONFIG_FILE = "digikey_config.toml"

"""
The total number of records we should query from digikey to make our parts catalogue
The max number we can query at a time is 50. Thus, if we wanted 500 parts in our catalogue,
then we would need a total of 10 queries
"""
DIGIKEY_QUERY_NUMBER = 100
DIGIKEY_MAX_QUERY = 50

class DigikeyAPIHook:
    def __init__(self, config_file=DIGIKEY_CONFIG_FILE, default_configs=None):
        self.config_file = config_file
        self.digikey_configs: dict[str, Any] = {}
        self.digikey_field_mapping: dict[str, Any] = {}
        self.digikey_component_handlers: dict[str, Any] = {}
        self.tracking_components: list[str] = []
        self.default_configs = default_configs
        self.logger = self._init_logger()

    # Digikey API logger from module, just use instead of printf for our own logging
    def _init_logger(self):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        digikey_logger = logging.getLogger('digikey')
        digikey_logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        digikey_logger.addHandler(handler)
        return logger

    def init(self):
        os.environ['DIGIKEY_CLIENT_ID'] = 'NAVpdHxEAMGBdnP3yai01cA8plVLyYovhLsCaPxX8jVSOSuT'
        os.environ['DIGIKEY_CLIENT_SECRET'] = 'ZU6YBcS1uqukd0KGGcljtmPE2ZOtMLGtcP9IPKSYtHap5WA1PU0Htcj24NNpEXQb'
        os.environ['DIGIKEY_CLIENT_SANDBOX'] = 'False'
        os.environ['DIGIKEY_STORAGE_PATH'] = "/home/andrew-streng/projects/pcb-front-end/cache"

        with open(self.config_file, "rb") as config:
            self.digikey_configs = tomllib.load(config)

        if not self.digikey_configs:
            self.logger.error("Error loading digikey configs")
            return

        self.tracking_components = self.digikey_configs["components"]["tracking"]

        for component in self.tracking_components:
            handler_path = self.digikey_configs[component]["handler"]
            module_name, function_name = handler_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            func = getattr(module, function_name)
            self.digikey_component_handlers[component] = func

    def get_component_list(self):
        return self.digikey_configs.get("components", {})

    def update_parts_catalogue(self):
        if not self.digikey_configs:
            self.logger.warning("Digikey config TOML not provided")
            return None

        parts_to_database = {}

        for component in self.tracking_components:
            keywords = self.digikey_configs[component]["keywords"]
            search_keywords = ",".join(keywords)
            current_record_pos = 0
            product_list = []

            if search_keywords:

                # We can only take 50 at a time
                # With the API we can paginate in order to get more 'new' results than 50
                while current_record_pos < DIGIKEY_QUERY_NUMBER:

                    search_request = KeywordRequest(keywords=search_keywords, limit=DIGIKEY_MAX_QUERY,
                                                    offset = current_record_pos)
                    response = digikey.keyword_search(body=search_request)

                    if response:
                        product_list.append(response.products)
                    
                    current_record_pos += DIGIKEY_MAX_QUERY

                if len(product_list) == 0:
                    continue

                handler = self.digikey_component_handlers.get(component)

                with open("databases/test_results.txt", 'w') as f:
                    f.write(str(product_list))

                if handler:
                    i = 0

                    for products in product_list:
                        database_content, prices = handler(products, self.digikey_configs)

                        if i > 0:
                            database_content.pop(0)

                        database_path = get_database_for_component(self.default_configs,component)
                        prices_path = database_path.replace(".csv", "") 
                        prices_path += "_prices" + ".csv"

                        if database_content:
                            try:
                                with open(database_path, "a" if i > 0 else "w") as csv_file:
                                    csv_writer = csv.writer(csv_file)
                                    csv_writer.writerows(database_content)
                                    parts_to_database[component] = csv_file

                                with open(prices_path, "a" if i > 0 else "w") as prices_csv:
                                    csv_writer = csv.writer(prices_csv)
                                    csv_writer.writerows(prices)

                            except FileNotFoundError:
                                self.logger.error("Database path not found for component: %s", component)
                        else:
                            self.logger.error("Error parsing data for component: %s", component)
                        
                        i = i + 1
        return API_SUCCESS