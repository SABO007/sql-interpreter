import openai

import json

import psycopg2

import os

import ast

import re

import time

import datetime

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', None)
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', None)
OPENAI_API_TYPE = os.getenv('OPENAI_API_TYPE', None)
TEMPERATURE = int(os.getenv('TEMPERATURE', 0))
STOP = os.getenv('STOP', "")
MAX_TOKENS = int(os.getenv('MAX_TOKENS', 500))
TOP_P = int(os.environ.get('TOP_P', 1))
FREQUENCY_PENALTY = int(os.getenv('FREQUENCY_PENALTY', 0))
PRESENCE_PENALTY = int(os.getenv('PRESENCE_PENALTY', 0))
N_RESP = int(os.getenv('N_RESP', 1))
TIMEOUT = int(os.getenv('TIMEOUT', 60))

DB_HOST = os.environ.get('DB_HOST', None)
DB_PORT = os.environ.get('DB_PORT', None)
DB_USER = os.environ.get('DB_USER', None)
DB_PASSWORD = os.environ.get('DB_PASSWORD', None)
DB_NAME = os.environ.get('DB_NAME', None)

PostGREScreds={'Host': DB_HOST, 'Port': DB_PORT, 'User': DB_USER, 'Password': DB_PASSWORD, 'Name': DB_NAME}

Creds = list(PostGREScreds.values())

sql={"sql":"SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public';"}


sql_key = list(sql.keys())

base_user_prompt = open('config/user_prompt.txt', 'r').read()

input_prompt=input("Enter the input prompt: ") #user input

system_prompt = open('config/system_prompt.txt', 'r').read()
system_prompt = system_prompt.replace('<input>', input_prompt)

history = "Empty"
user_prompt = base_user_prompt.replace('<history>', history[0])

current_time = datetime.datetime.now()
current_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
user_prompt = user_prompt.replace('<DateTime>', current_time)

def automate_function_call(Creds, sql_key, response_message):

    """Function calling for Running the generated python code on PostGRES Server"""


    conn = psycopg2.connect(host=Creds[0], database=Creds[4], user=Creds[2], password=Creds[3], port=Creds[1])
    
    def extract_outermost_dict(s):
        for i in range(len(s)):
            for j in range(i, len(s)):
                substring = s[i:j+1]
                try:
                    node = ast.literal_eval(substring)
                    if isinstance(node, dict):
                        return node
                except (ValueError, SyntaxError):
                    pass
        return None
    
    def extract_json(response_message):
        """Function to extract JSON from the output response. The JSON is within triple bacticks

        Args:
            output_response (str): output response

        Returns:
            dict: json
        """
        json_output = re.findall(r"```([\s\S]*?)```", response_message)

        if len(json_output) == 0:
            return ''
        elif len(json_output) >= 1:
            json_output = json_output[0]
        
        json_output = extract_outermost_dict(json_output)
        return json_output
    
    def validate_json(self, input_json):
        return True, "The JSON is valid"

    json_output = extract_json(response_message)

    def ExecuteSQL(sql_key):
        """Function to execute SQL query

        Args:
            sql (str): sql query to execute

        Returns:
            str: output of sql query
        """
        try:
            sql = sql[sql_key[0]] #key
            cur = conn.cursor()
            # Execute a SQL query
            cur.execute(sql)

            # Fetch the results
            results = cur.fetchall()

            # Close the cursor and connection
            cur.close()
            if results == '':
                return "PostgresSQL Query executed Successfully"
            else:
                ShareOutput(results)
                return results
        except Exception as e:
            return f"There is some error in SQL query: {str(e)}"
    
    def get_database_info(sql_key):
        """Function to get database and table information using sql queries

        Returns:
            dict: database info
        """
        try:
            result = ExecuteSQL(sql_key)
            update_history({"function":"ExecuteSQL","parameters":{"sql":"SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public';"}}, result)
        except Exception as e:
            raise e

    def ShareOutput(output: str) -> str:
        """Function to share output

        Args:
            output (str): output to share

        Returns:
            str: output of sharing output
        """
        try:
            return output
        except Exception as e:
            return e

    def update_history(input_json: str, output: str) -> str:
        """
        Function to update history

        Args:
            input_prompt (str): input prompt
            output (str): output

        Returns:
            str: output of updating history
        """
        try:
            history = prepare_history(input_json, output)
            if history == "Empty":
                history = [history]
            else:
                history.append(history)
            
            for ind, his in enumerate(history, start=1):
                history += f"{ind}. {his}\n"

            user_prompt = base_user_prompt.replace('<history>', f"[{history}]")
        except Exception as e:
            raise e
        
    def prepare_history(input_json: str, output: str) -> str:
        """Function to prepare history

        Args:
            input_prompt (str): input prompt
            output (str): output

        Returns:
            str: output of preparing history
        """
        try:
            return f"Assistant Response-\n{input_json}\nExecution Output-\n{output}\n"
        except Exception as e:
            raise e


    get_database_info(sql_key)

    time.sleep(2)

    if json_output == '':
        print(response_message)
        # break

    valid_json, output = validate_json(json_output)


    if not valid_json:
        update_history(response_message, output)
        # continue

    function_to_perform = json_output['function']

    if 'parameters' in json_output:
        function_params = json_output['parameters']

    # if function_to_perform == "Exit":
        # break

    supported_functions = {
            "ExecuteSQL": ExecuteSQL,
            "ShareOutput": ShareOutput
        }
    
    output = supported_functions[function_to_perform](function_params)
    print(output)
    
    update_history(response_message, output)
    
    arguments = {

        "Creds": Creds,

        "sql_key": sql_key,

        "response_message": response_message,

    }
    
    return json.dumps(arguments) 


 

def run_conversation(system_prompt, user_prompt):
    # Step 1: send the conversation and available functions to GPT
    messages = [{"role":"system", "content": system_prompt}, {"role":"user", "content": user_prompt}]
    functions = [
        {
            "name": "automate_function_call",
            "description": "Automate the function calling in such a way that history is updated",
            "parameters": {
                "type": "object",
                "properties": {
                    "Creds": {
                        "type": "list",
                        "description": "Credentials for PostGRES which are used in the function using psycopg2 library",
                    },
                    "sql_key": {
                        "type": "string",
                        "description": "The key for the SQL Query to be executed  "
                    },
                    "response_message": {
                        "type": "string",
                        "description": "First response of GPT API for system_prompt and user_prompt"
                    },
                },
                "required": ["Creds", "sql_key", "response_message"]
            }
        }, 

    ]

    response = openai.ChatCompletion.create(

        engine="DIR_GPT4",

        messages=messages,

        temperature=TEMPERATURE,

        max_tokens=MAX_TOKENS,

        top_p=TOP_P,

        frequency_penalty=FREQUENCY_PENALTY,
        
        presence_penalty=PRESENCE_PENALTY,

        functions=functions,

        function_call="auto", # Function calling will not automated if it is set as "none"

    )

    response_message = response["choices"][0]["message"]




    if response_message.get("function_call"):

        available_functions = {

            "automate_function_call": automate_function_call,

        }

        function_name = response_message["function_call"]["name"]

        fuction_to_call = available_functions[function_name]

        function_args = json.loads(response_message["function_call"]["arguments"])

        function_response = fuction_to_call(


            Creds=function_args.get("Creds"),

            sql_key=function_args.get("sql_key"),

            response_message=function_args.get("response_message"),

        )

        messages.append(response_message)

        messages.append(

            {

                "role": "function",

                "name": function_name,

                "content": function_response,

            }

        )

        second_response = openai.ChatCompletion.create(

            engine="DIR_GPT4",

            messages=messages,

        )

        return second_response


if OPENAI_API_TYPE == 'azure':
    openai.api_base = OPENAI_BASE_URL
    openai.api_key = OPENAI_API_KEY
    openai.api_type = OPENAI_API_TYPE
    openai.api_version = "2023-03-15-preview"
else:
    openai.api_key = OPENAI_API_KEY


print(run_conversation(system_prompt, user_prompt))