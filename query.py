from digikey_query import DigikeyAPIHook, DIGIKEY_CONFIG_FILE
from digikey_part_handlers import DIGIKEY_FIELD_TO_HEADER
from components import *
from headers import *
import threading
import pandas as pd
import openai
import faiss
import pickle 
import numpy as np
import csv

openai.api_key = "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"

class Query:

    def __init__(self, api=API_DIGIKEY, remake_query = False, results = 10):
        self.api: int = api
        self.default_configs: Any = self._init_default_configs()
        self.component_embeddings: dict[str, Any] = {}
        self.api_configs: dict[str, Any] = self.load_api_configs()
        self.remake_query: bool = remake_query
        self.indices: dict[str, list] = {}
        self.results_to_consider: int = results
        self.field_to_header: dict[str,str] = self.init_field_header_mapping()
        self.standard_pricing_mode:int = 0
        self.bom_format:int = BOM_FORMAT_KICAD
        self.current_rows:Any = None

    def _init_default_configs(self):
        try:
            with open(DEFAULT_CONFIG_FILE, "rb") as config:
                config =  tomllib.load(config)
        except:
            config = None
        return config
    
    def init_field_header_mapping(self):

        if self.api == API_DIGIKEY:
            return DIGIKEY_FIELD_TO_HEADER

    def get_default_configs(self):
        return self.default_configs

    def get_bom_format(self):
        return self.bom_format
    
    def get_api(self):
        return self.api

    def get_current_rows(self):
        return self.current_rows
    
    def initialize_parts_query_engine(self):

        target = None

        if self.api == API_DIGIKEY:
            if self.remake_query:
                target = self.prepare_component_library
            else:
                target = self.prepare_component_library_from_database

        if target:
            init_thread = threading.Thread(target=target)
            init_thread.start()

    def get_embedding(self, text, model="text-embedding-3-small"):
        embedding = openai.embeddings.create(input=[text], model=model)
        return embedding.data[0].embedding

    def load_api_configs(self):
        api_configs = {}

        with open(DIGIKEY_CONFIG_FILE, "rb") as dk_config:
            api_configs[API_DIGIKEY] = tomllib.load(dk_config)
        return api_configs
    
    def get_components_list(self):
        if self.api == API_DIGIKEY:
            return self.api_configs[API_DIGIKEY]["components"]["tracking"]
        
    def get_database_for_component(self, component):
        if self.api == API_DIGIKEY:
            return self.default_configs["digikey-databases"][component]
        
    def get_pricing_database_for_component(self, component):
        if self.api == API_DIGIKEY:
            return self.default_configs["digikey-pricing-databases"][component]
        
    def get_standard_pricing_data(self, component, index):
        if self.api == API_DIGIKEY:
            # TODO typedef
            if self.standard_pricing_mode == 0:
                return self.indices[component]["pricing"][index][0]
            elif self.standard_pricing_mode == 1:
                return self.indices[component]["pricing"][index][1]
            else:
                return self.indices[component]["pricing"][index][2]
    
    def load_pricing_database(self, database):
        data = []
        try:
            with open(database, mode='r', newline='') as file:
                csv_reader = csv.reader(file)
                headers = next(csv_reader)

                for rows in csv_reader:
                    data.append(rows)

        except FileNotFoundError:
            return None
        
        return data

    # This would need to be invoked for whenever the database changes
    def generate_new_embeddings_for_components(self):
    
        components = self.get_components_list()

        if components is not None:
        
            for component in components:
                db = self.get_database_for_component(component)

                if db is not None:
                    embeddings,rows, positions = self.prepare_component_library(db)
                    pricing_db = self.get_pricing_database_for_component(component)
                    pricing_data = self.load_pricing_database(pricing_db) if pricing_db else None  

                    
                    self.component_embeddings[component] = {
                        "embeddings": embeddings,
                        "rows": rows,
                        "header_positions": positions,
                        "pricing": pricing_data
                    }

            self.save_embeddings()

        else:
            print("Cannot generate new embeddings - no components!")

    def save_embeddings(self):
        embeddings_file = self.default_configs["embeddings-file"]["file"]
        with open(embeddings_file, "wb") as embedding_file:
            pickle.dump(self.component_embeddings, embedding_file)
        

    def load_embeddings(self):
        embeddings_file = self.default_configs["embeddings-file"]["file"]
        
        with open(embeddings_file, "rb") as embedding_file:
            embeddings = pickle.load(embedding_file)

        return embeddings

    def convert_embeddings_to_index(self, embeddings:Any):
        embeddings_matrix = np.array(embeddings).astype("float32")
        index = faiss.IndexFlatL2(len(embeddings_matrix[0]))
        index.add(embeddings_matrix)
        return index 
    
    def format_row(self, data):
        if self.api == API_DIGIKEY:
            formatted_row = digikey_query.format_row(data)


    def prepare_component_library(self, component_library):
    
        print(f"Preparing component lib for {component_library}")
        component_embeddings = []
        rows = []
        header_positions = {}
        text = ""

        # TODO maybe this should be read in chunks as to avoid memory overflow
        # If the CSV is larger than the available memory on the system

        with open(component_library, mode='r', newline='') as file:
            csv_reader = csv.reader(file)
            headers = next(csv_reader)

            for i in range(len(headers)):
                try:
                    mapping = self.field_to_header[headers[i]]

                    if mapping:
                        header_positions[mapping] = i   
                except KeyError:
                    continue
            # Iterate over each row in the CSV file
            for row in csv_reader:
                
                text = ' '.join(row)
                embedding = self.get_embedding(text)
                component_embeddings.append(embedding)
                rows.append(row)
                text = ""

        # For the list of embeddings, create an index
        # See https://python.langchain.com/docs/integrations/vectorstores/faiss/
        # FAISS L2 norm requires embeddings to be in matrix form
        # It also requires you to specify the dimensions of the matrix
        # For OpenAI embeddings, this is 1536
        embeddings_matrix = np.array(component_embeddings).astype("float32")
        index = faiss.IndexFlatL2(len(embeddings_matrix[0]))
        index.add(embeddings_matrix)

        return [component_embeddings, rows, header_positions]

    def prepare_component_library_from_database(self):
        all_embeddings = self.load_embeddings()

        # Build an index for each component
        component_list = self.get_components_list()
        
        for component in component_list:
            component_embeddings = all_embeddings[component]["embeddings"]
            rows = all_embeddings[component]["rows"]
            positions = all_embeddings[component]["header_positions"]
            pricing_data = all_embeddings[component]["pricing"]

            if component_embeddings:
                component_index = self.convert_embeddings_to_index(component_embeddings)
                self.indices[component] = {
                    "index": component_index,
                    "rows": rows,
                    "header_positions" : positions,
                    "pricing" : pricing_data 
                }

        print("Components library completed")

    def do_query(self, query:str):

        print("Doing query ", query)
        embedding = self.get_embedding(query)
        query_vector = np.array([embedding]).astype("float32")

        # Determine which index we should query
        search_index = self.indices["resistor"]["index"]
        rows = self.indices["resistor"]["rows"]
        distances,indices = search_index.search(query_vector, self.results_to_consider)
        flat_indices = np.array(indices).flatten().tolist()
        # flat_distances = np.array(distances).flatten().tolist()

        found_data = []
        for index in flat_indices:
            found_data.append(rows[index])

        return self.prepare_rows("resistor", found_data) 

    def prepare_rows(self, component, rows):
        positions = self.indices[component]["header_positions"]
        rows_len = len(rows)
        data = []

        if rows_len <= 0:
            return data

        for i in range(rows_len):
            data_map = {}
            for header in HEADER_LISTING:

                if header == HEADER_STANDARD_PRICING:
                    data_map[header] = self.get_standard_pricing_data(component, i)
                else:
                    try:
                        index = positions[header]

                        if index < rows_len:
                            data_map[header] = rows[i][index]

                    except KeyError:
                        pass
                
            data.append(data_map)

        self.current_rows = data
        return data

    # When a new reference designator (say R24) has been clicked, just return the 
    # rows in the catalogue corresponding to the designator, in this case, resistor
    def do_designator_query(self, designator: str):

        data = []
        rows = []
        positions = {}
        component = ""

        if designator.startswith("R"):
            component = COMPONENT_TOML_MAPPING_ID[COMPONENT_RESISTOR]
        elif designator.startswith("L"):
            component = COMPONENT_TOML_MAPPING_ID[COMPONENT_INDUCTOR]
        elif designator.startswith("C"):
            component = COMPONENT_TOML_MAPPING_ID[COMPONENT_CAPACITOR]
        else:
            print("Unsupported designator!")

        rows = self.indices[component]["rows"]
        return self.prepare_rows(component, rows)
        # rows_len = len(rows)

        # if rows_len <= 0:
        #     return data

        # for i in range(rows_len):
        #     data_map = {}
        #     for header in HEADER_LISTING:

        #         if header == HEADER_STANDARD_PRICING:
        #             data_map[header] = self.get_standard_pricing_data(component, i)
        #         else:
        #             try:
        #                 index = positions[header]

        #                 if index < rows_len:
        #                     data_map[header] = rows[i][index]

        #             except KeyError:
        #                 pass
                
        #     data.append(data_map)

        # return data

q = Query()
digikey_query = DigikeyAPIHook(default_configs=q.get_default_configs())

if __name__ == "__main__":


    digikey_query.init()
    digikey_query.update_parts_catalogue()
    q.generate_new_embeddings_for_components()
    # q.initialize_parts_query_engine()
    q.prepare_component_library_from_database()
    # print("Starting query")
    # q.do_query("Manufacturer is Yageo")
    # q.do_query("Panasonic Electronic Components 10000 for 45.8")
    # q.do_query("10 kOhms YAGEO 5000 for 15.3")
    # q.do_designator_query("R4")
    # q.do_query("KOA Speer Electronics 10 kOhms 0.1W 5000 for 22.1")