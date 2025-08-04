from digikey_query import DigikeyAPIHook, DIGIKEY_CONFIG_FILE
from digikey_part_handlers import get_regex, DIGIKEY_FIELD_TO_HEADER, NORMALIZED_FIELDS, NORMALIZED_HEADER
from components import *
from headers import *
import threading
import openai
import faiss
import pickle 
import numpy as np
import csv
import re
import hashlib
from digikey_fields import *
import time

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
    
    def initialize_parts_query_engine(self, join=False):

        target = None

        if self.api == API_DIGIKEY:
            if self.remake_query:
                target = self.make_new
            else:
                target = self.prepare_component_library_from_database

        if target:
            init_thread = threading.Thread(target=target)
            init_thread.start()

            if join:
                init_thread.join()


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

    def generate_search_embeddings(self):

        embeddings = []

        for component in COMPONENT_SPECIFIC:
            embeddings.append(self.get_embedding(component))

        return embeddings
    
    def make_new(self):

        self.generate_new_embeddings_for_components()

    # This would need to be invoked for whenever the database changes
    def generate_new_embeddings_for_components(self):
    
        components = self.get_components_list()

        if components is not None:
        
            for component in components:
                db = self.get_database_for_component(component)

                if db is not None:
                    embeddings,rows, positions, semantics= self.prepare_component_library(db)
                    pricing_db = self.get_pricing_database_for_component(component)
                    pricing_data = self.load_pricing_database(pricing_db) if pricing_db else None 
                    
                    self.component_embeddings[component] = {
                        "embeddings": embeddings,
                        "rows": rows,
                        "header_positions": positions,
                        "pricing": pricing_data,
                        "semantics": semantics
                    }

                    
            self.component_embeddings[COMPONENT_ANY] = {
                "embeddings": self.generate_search_embeddings()
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
        em = np.array(embeddings).astype("float32")
        # index = faiss.IndexFlatL2(len(embeddings_matrix[0]))
        faiss.normalize_L2(em)
        index = faiss.IndexFlatIP(em.shape[1])
        # index.add(embeddings_matrix)
        index.add(em)
        return index 
    
    def format_row(self, data):
        if self.api == API_DIGIKEY:
            formatted_row = digikey_query.format_row(data)


    def hash_value(self, val):
        return int(hashlib.sha256(str(val).encode()).hexdigest(), 16)
        

    def prepare_component_library(self, component_library):
    
        print(f"Preparing component lib for {component_library}")
        component_embeddings = []
        rows = []
        header_positions = {}
        text = ""
        semantics = []
        upper_semantics = []
        semantic_mapping = {}
        qualifier = ""

        with open("semantics.txt",mode = 'r') as file:

            semantic_upper = False
            for line in file:

                if semantic_upper:
                    upper_semantics.append(line.strip())
                else:
                    semantics.append(line.strip())

                if line.strip() == "====":
                    semantic_upper = True


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
                
                i = 0
                for contents in row:
                    
                    header_present = SEMANTIC_HEADERS.get(headers[i])

                    if not header_present:
                        i = i + 1
                        continue

                    do_hash = False

                    if not contents.startswith("https") and not contents.startswith("//mm.digikey") and not headers[i] == "standard_pricing":
                        
                        header = headers[i]

                        if header == "quantity_available":
                            
                            if contents:
                                contents = normalize_qty(contents)
 
                        # if header in NORMALIZED_FIELDS:
                        contents = contents.replace("µ", "u")
                            # contents = contents.replace("V", "")
                        contents = contents.replace("W", "")

                        if header == FIELD_FOOTPRINT:
                            contents = normalize_footprint("r",contents)
                            qualifier = f"{header}:{contents}"
                            do_hash = True
                        elif header == FIELD_TOLERANCE:
                            contents = normalize_tolerance(contents)
                            qualifier = f"{header}:{contents}"
                            do_hash = True
                        elif header == FIELD_TEMP_COEFF:
                            qualifier = f"{header}: {contents}"
                            do_hash = True
                        elif header == FIELD_POWER:
                            contents = normalize_power(contents)
                            qualifier = f"{header}: {contents}"
                            do_hash = True
                        elif header == FIELD_VR or header == FIELD_VOLTAGE_OUT or header == FIELD_CURRENT_OUT:
                            qualifier = f"{header}:{contents}"
                            do_hash = True
                        elif header == FIELD_FREQUENCY_STABILITY or header == FIELD_FREQUENCY_STABILITY \
                            or header == FIELD_FREQUENCY_TOLERANCE or header == FIELD_FREQUENCY:
                            contents = contents.replace("±", "")
                            qualifier = f"{header}:{contents}"
                            do_hash = True
                        elif header == FIELD_PRODUCT_STATUS or header == FIELD_APPLICATION:
                            do_hash = False
                        elif header == FIELD_MANUFACTURER:
                            do_hash = False
                        elif header == FIELD_TYPE:
                            contents = contents.split(" ")[0]
                            print("CONTENTS", contents)
                            qualifier = f"{header}:{contents}"
                            do_hash = True
                        elif is_flash_field(header):
                            contents = normalize_flash_field(header, contents)
                            qualifier = f"{header}:{contents}"
                            do_hash = True

                            # print(contents)
                        else:

                            print("CONTENTS ABOUT TO SEARCH", contents)
                                # pattern = re.compile(r"\b[0-9]+\s[A-Za-z]+\b", re.IGNORECASE)
                            pattern = re.compile(get_regex(header), re.IGNORECASE)
                            match = pattern.search(contents)

                            if match:
                                    
                                    items = match.group().split(" ")
                                    unit = items[1].upper()
                                    val = items[0]
                                    norm_unit = MULTIPLIERS.get(unit)
                                    norm_val = float(val) * norm_unit
                                    # contents = str(norm_val) + " F"

                                    sem_hash = self.hash_value(str(norm_val))
                                    
                                    index = sem_hash % len(semantics)
                                    semantic_val = semantics[index]
                                    # semantic_mapping[val] = semantic_val

                                    sem_hash = self.hash_value(match.group())
                                    index = sem_hash % len(upper_semantics)
                                    upper_val = upper_semantics[index]

                                    semantic_val = f"{semantic_val} {upper_val}"
                                    semantic_mapping[match.group()] = semantic_val                                    
                                    
                                    if semantic_val:
                                        contents = semantic_val
                                    else:
                                        contents = SEMANTICS.get(items[1].upper())
                        if do_hash:
                            print("DOING HASH", contents, qualifier)
                            sem_hash = self.hash_value(contents)
                            index = sem_hash % len(semantics)
                            semantic_val = semantics[index]
                            sem_hash = self.hash_value(qualifier)
                            index = sem_hash % len(upper_semantics)
                            semantic_val = f"{semantic_val} {upper_semantics[index]}"
                            semantic_mapping[contents] = semantic_val
                            contents = semantic_val

                        nom_header = NORMALIZED_HEADER.get(header)
                        
                        if nom_header:
                            header = nom_header

                        text += f"{header}:{contents};"
                        qualifier = ""
                    i = i + 1

                print(text)
                embedding = self.get_embedding(text)
                component_embeddings.append(embedding)
                rows.append(row)
                text = ""


        # For the list of embeddings, create an index
        # See https://python.langchain.com/docs/integrations/vectorstores/faiss/
        # FAISS L2 norm requires embeddings to be in matrix form
        # It also requires you to specify the dimensions of the matrix
        # For OpenAI embeddings, this is 1536

        """
        Code for Euclidean distance indexing
        """
        # embeddings_matrix = np.array(component_embeddings).astype("float32")
        # index = faiss.IndexFlatL2(len(embeddings_matrix[0]))
        # index.add(embeddings_matrix)

        embeddings_matrix = np.array(component_embeddings).astype("float32")
        faiss.normalize_L2(embeddings_matrix)
        index = faiss.IndexFlatIP(embeddings_matrix.shape[1])
        index.add(embeddings_matrix)

        print(semantic_mapping)
        with open("semantic_mapping.txt", 'w') as file:

            for mapping in semantic_mapping:
                file.write(f"{mapping} - {semantic_mapping[mapping]}")
                file.write("\n")
        return [component_embeddings, rows, header_positions, semantic_mapping]

    def prepare_component_library_from_database(self):
        all_embeddings = self.load_embeddings()

        # Build an index for each component
        component_list = self.get_components_list()
        
        for component in component_list:
            component_embeddings = all_embeddings[component]["embeddings"]
            rows = all_embeddings[component]["rows"]
            positions = all_embeddings[component]["header_positions"]
            pricing_data = all_embeddings[component]["pricing"]
            semantics = all_embeddings[component]["semantics"]

            if component_embeddings:
                component_index = self.convert_embeddings_to_index(component_embeddings)
                self.indices[component] = {
                    "index": component_index,
                    "rows": rows,
                    "header_positions" : positions,
                    "pricing" : pricing_data,
                    "semantics": semantics
                }

        search_embeddings = all_embeddings[COMPONENT_ANY]["embeddings"]
        search_index = self.convert_embeddings_to_index(search_embeddings)
        self.indices[COMPONENT_ANY] = {
            "index": search_index
        }

        print("Components library completed")

    def normalize_query(self, query):
        embedding = self.get_embedding(query)
        query_vector = np.array([embedding]).astype("float32")
        faiss.normalize_L2(query_vector)

        return query_vector
    
    def do_search(self, component,query_vector):
        if component:
            search_index = self.indices[component]["index"]
            rows = self.indices[component]["rows"]
            distances,indices = search_index.search(query_vector, self.results_to_consider)
            flat_indices = np.array(indices).flatten().tolist()
            flat_distances = np.array(distances).flatten().tolist()

            found_data = []
            for index in flat_indices:
                found_data.append(rows[index])

            return [self.prepare_rows(component, found_data), flat_indices, flat_distances]
        else:
            print("Invalid component to do query")

    def pre_normalize_query(self,component, q):

        # re_match = re.match(r"[0-9]+\.[0-9]+\s[A-Za-z][A-Za-z]", "0.1 uF", re.IGNORECASE)
        # re_match = re.match(VALUE_REGEX, q, re.IGNORECASE)

        queries = q.split(",")
        query_list = []
        test = ""
        print("QUERIES ", queries)

        for query in queries:

            # pattern = re.compile(r"\b[0-9]+\s[A-Za-z]+\b", re.IGNORECASE)
            pattern = re.compile(get_regex(FIELD_CAPACITANCE), re.IGNORECASE)
            match = pattern.search(query)
            val_semantics = self.indices[component]["semantics"]

            if match:
                
                print("GROUP", match.group())
                norm_val = val_semantics[match.group()]
                q = "Clock Frequency " + norm_val
                # query_list.append(norm_val)
                # replaced = pattern.sub(str(norm_unit), q)
            else:
                
                items = query.split(" ")
                print("ITEMS", items)

                if len(items) == 1:
                    q = items[0]
                
                else:

                    norm_val = items[1]
                    sem = val_semantics.get(norm_val)
                    if sem:
                        norm_val = val_semantics[norm_val]
                    else:
                        items_len = len(items)
                        i = 2

                        while i < items_len:
                            norm_val += " " + items[i]
                            i = i + 1
                        
                
                    print("NORM VAL ", norm_val)
                    q = f"{items[0]} {norm_val}"

            test += q + " "

        print(test)
        return test

    def do_query(self, query:str, designator:str, auto_bom = False):

        component = self.designator_to_component(designator)

        if component is COMPONENT_ANY:
            query_vector = self.normalize_query(query)
            search_index = self.indices[COMPONENT_ANY]["index"]
            distances,indices = search_index.search(query_vector, self.results_to_consider)
            flat_indices = np.array(indices).flatten().tolist()
            flat_distances = np.array(distances).flatten().tolist()
            best_search = flat_indices[0]

            if best_search <= len(COMPONENT_SPECIFIC_NAME):
                queries = self.pre_normalize_query(COMPONENT_SPECIFIC_NAME[best_search], query)
                query_vector = self.normalize_query(queries)
                results, indices, flat_distances = self.do_search(COMPONENT_SPECIFIC_NAME[best_search], query_vector)

                return [results, indices, flat_distances]
        else:
            queries = self.pre_normalize_query(self.designator_to_component(designator), query)
            embedding = self.get_embedding(queries)
            print("Pre-norm query ", queries)
            query_vector = np.array([embedding]).astype("float32")
            faiss.normalize_L2(query_vector)

            results, indices, distances = self.do_search(component, query_vector)

            return [results,indices, distances]

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

                        if int(index) <= len(rows[i]):
                            data_map[header] = rows[i][index]

                    except KeyError:
                        pass
                
            data.append(data_map)

        self.current_rows = data
        return data

    def designator_to_component(self, designator):
        component = None

        if designator.startswith("R"):
            component = COMPONENT_TOML_MAPPING_ID[COMPONENT_RESISTOR]
        elif designator.startswith("L"):
            component = COMPONENT_TOML_MAPPING_ID[COMPONENT_INDUCTOR]
        elif designator.startswith("C"):
            component = COMPONENT_TOML_MAPPING_ID[COMPONENT_CAPACITOR]
        elif designator.startswith("Y"):
            component = COMPONENT_TOML_MAPPING_ID[COMPONENT_CRYSTAL]
        elif designator.startswith("U"):
            component = COMPONENT_ANY
        elif designator.startswith("J"):
            component = COMPONENT_ANY

        return component

    # When a new reference designator (say R24) has been clicked, just return the 
    # rows in the catalogue corresponding to the designator, in this case, resistor
    def do_designator_query(self, designator: str):
        rows = []
        component = self.designator_to_component(designator)

        if component is COMPONENT_ANY:
            return None
        else:
            rows = self.indices[component]["rows"]
        
        return self.prepare_rows(component, rows)

    def print_results(self, results):

        for result in results:
            print(result)
        
    def print_results_key(self, results, keys):

        for result in results:
            
            text = ""
            for key in keys:
                text += result.get(key) + " "
            
            print(text)


q = Query()                  
digikey_query = DigikeyAPIHook(default_configs=q.get_default_configs())

def main():
    q.prepare_component_library_from_database()
    results, indices, _ = q.do_query("Manufacturer YAGEO,Resistance 100 kOhms","R1", True)
if __name__ == "__main__":
    main()