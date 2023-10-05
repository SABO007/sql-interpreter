from config.envs import OPENAI_API_TYPE, OPENAI_BASE_URL, OPENAI_API_KEY, TEMPERATURE, STOP, MAX_TOKENS, TOP_P, FREQUENCY_PENALTY, PRESENCE_PENALTY, N_RESP, TIMEOUT, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
import psycopg2
import json
import openai
import datetime
import re
import ast
import time


# Establish a connection to the PostgreSQL server
conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT)

if OPENAI_API_TYPE == 'azure':
    openai.api_base = OPENAI_BASE_URL
    openai.api_key = OPENAI_API_KEY
    openai.api_type = OPENAI_API_TYPE
    openai.api_version = "2023-07-01-preview"
else:
    openai.api_key = OPENAI_API_KEY


class sqlInterprert():

    def __init__(self, input_prompt, model):
        self.model = model
        self.input_prompt = input_prompt
        self.user_prompt1 = open('config/user_prompt1.txt', 'r').read()
        self.system_prompt1 = open('config/system_prompt1.txt', 'r').read()
        self.system_prompt = open('config/system_prompt.txt', 'r').read()
        self.base_user_prompt = open('config/user_prompt.txt', 'r').read()
        self.system_prompt = self.system_prompt.replace('<input>', self.input_prompt)
        self.history = "Empty"
        self.user_prompt = self.base_user_prompt.replace('<history>', self.history[0])
        self.current_time = datetime.datetime.now()
        self.current_time = self.current_time.strftime("%Y-%m-%d %H:%M:%S")
        self.user_prompt = self.user_prompt.replace('<DateTime>', self.current_time)

    def ExecuteSQL(self, sql) -> str:
        """Function to execute SQL query

        Args:
            sql (str): sql query to execute

        Returns:
            str: output of sql query
        """
        sql="SELECT * from Employees;"

        try:
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
                self.ShareOutput(results)
                return results
        except Exception as e:
            return f"There is some error in SQL query: {str(e)}"
    
    def ShareOutput(self, output: str) -> str:
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

    
    def extract_outermost_dict(self, s):
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

    def extract_json(self, output_response):
        """Function to extract JSON from the output response. The JSON is within triple bacticks

        Args:
            output_response (str): output response

        Returns:
            dict: json
        """
        json_output = re.findall(r"```([\s\S]*?)```", output_response)

        if len(json_output) == 0:
            return ''
        elif len(json_output) >= 1:
            json_output = json_output[0]
        
        json_output = self.extract_outermost_dict(json_output)
        # print(json_output)
        # json_output = json.loads(json_output)
        return json_output
    
    def update_history(self, input_json: str, output: str) -> str:
        """
        Function to update history

        Args:
            input_prompt (str): input prompt
            output (str): output

        Returns:
            str: output of updating history
        """
        try:
            history = self.prepare_history(input_json, output)
            if self.history == "Empty":
                self.history = [history]
            else:
                self.history.append(history)
            
            for ind, his in enumerate(self.history, start=1):
                history += f"{ind}. {his}\n"

            self.user_prompt = self.base_user_prompt.replace('<history>', f"[{history}]")
        except Exception as e:
            raise e

    def prepare_history(self, input_json: str, output: str) -> str:
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

    def get_database_info(self):
        """Function to get database and table information using sql queries

        Returns:
            dict: database info
        """
        try:
            result = self.ExecuteSQL("SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public';")
            self.update_history({"function":"ExecuteSQL","parameters":{"sql":"SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public';"}}, result)
        except Exception as e:
            raise e

    def function_call(self, sql, function_output):
        function_output =self.ExecuteSQL(sql)
        function_output = self.ShareOutput(function_output)

        arguments = {

            "sql_key": sql,

            "function_output": function_output

        }

        return json.dumps(arguments)
    
    def main(self):
        self.get_database_info()
        response = openai.ChatCompletion.create(
                engine=self.model,
                messages=[{"role":"system", "content":self.system_prompt}, {"role":"user", "content":self.user_prompt}],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                top_p=TOP_P,
                frequency_penalty=FREQUENCY_PENALTY,
                presence_penalty=PRESENCE_PENALTY,
                stop=STOP,
                timeout=TIMEOUT,
                n=N_RESP
            )
            
        output_response = response['choices'][0]['message']['content']
        print("output_response: ", output_response)

        json_output = self.extract_json(output_response)
        print("json_output: ", json_output)

        time.sleep(5)

        if json_output == '':
            print(output_response)

        valid_json, output = self.validate_json(json_output)

        if not valid_json:
            self.update_history(output_response, output)
        
        if 'parameters' in json_output:
            function_params = json_output['parameters']
        
        messages=[{"role":"system", "content":self.system_prompt1}, {"role":"user", "content":self.user_prompt1}]

        functions=[
            {
                    "name": "function_call",
                    "description": "The function which runs the SQL query on Postgres server and give back output",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "The SQL query which is executed on PostGRES server using psycopg2 library"
                            },

                            "function_output": {
                                "type": "string",
                                "description": "The output of the function 'automate_function_call' after executing two sub-functions 'ExecuteSQL', 'ShareOutput'. This is the output of the SQL query. "
                            },
                        },
                        "required": ["function_output"]
                    }
                }
                ]
    
        response = openai.ChatCompletion.create(
                engine=self.model,
                messages=messages,
                functions=functions,
                temperature=TEMPERATURE,
            )
            
        output_response = response['choices'][0]['message']

        if output_response.get("function_call"):
            available_functions = {

                "function_call": self.function_call,

            }

            function_name = output_response["function_call"]["name"]

            fuction_to_call = available_functions[function_name]

            function_args = json.loads(output_response["function_call"]["arguments"])

            function_response = fuction_to_call(

                sql=function_params,

                function_output=function_args.get("function_output")

            )

            print('function_response: ', function_response)

            # messages.append(output_response)

            messages.append(

                {

                    "role": "function",

                    "name": function_name,

                    "content": function_response,

                }

            )

            second_response = openai.ChatCompletion.create(
                            engine=self.model,
                            messages=messages,
            ) 
            output = second_response['choices'][0]['message']['content']

            print("\n")
            print( output)


if __name__ == "__main__":
    input_prompt = input("Enter the input prompt: ")
    model = "DIR_ChatBot_FC"
    sqlInterprert(input_prompt, model).main()       


