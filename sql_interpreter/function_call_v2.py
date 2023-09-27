import datetime
import time
import ast
import openai
import psycopg2
import re
import json
from config.envs import OPENAI_API_TYPE, OPENAI_BASE_URL, OPENAI_API_KEY, TEMPERATURE, STOP, MAX_TOKENS, TOP_P, FREQUENCY_PENALTY, PRESENCE_PENALTY, N_RESP, TIMEOUT, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

#python function
python_output="print('Hello World!')"

# Function call dictionaries
Creds={'Host': DB_HOST, 'Port': DB_PORT, 'User': DB_USER, 'Password': DB_PASSWORD, 'Name': DB_NAME}

sql={"sql": f"SELECT execute_python_script('{python_output}');"} #No dynamic change


# Function call dictionary keys
Creds_key = list(Creds.keys())

sql_key = list(sql.keys())

# setup openai
if OPENAI_API_TYPE == 'azure':
    openai.api_base = OPENAI_BASE_URL
    openai.api_key = OPENAI_API_KEY
    openai.api_type = OPENAI_API_TYPE
    openai.api_version = "2023-03-15-preview"
else:
    openai.api_key = OPENAI_API_KEY

class sqlInterprert():
    def __init__(self, input_prompt, max_steps, max_cost, model) -> None:
        self.input_prompt = input_prompt
        self.max_steps = max_steps
        self.max_cost = max_cost
        self.model = model
        self.system_prompt = open('config/system_prompt.txt', 'r').read()
        self.base_user_prompt = open('config/user_prompt.txt', 'r').read()
        self.system_prompt = self.system_prompt.replace('<input>', self.input_prompt)
        self.history = "Empty"
        self.user_prompt = self.base_user_prompt.replace('<history>', self.history[0])
        self.current_time = datetime.datetime.now()
        self.current_time = self.current_time.strftime("%Y-%m-%d %H:%M:%S")
        self.user_prompt = self.user_prompt.replace('<DateTime>', self.current_time)

    
    def ExecuteSQL(self, sql_key, Creds_key) -> str:
        """Function to execute SQL query

        Args:
            sql (str): sql query to execute

        Returns:
            str: output of sql query
        """
        
        # Establish a connection to the PostgreSQL server
        conn = psycopg2.connect(host=Creds[Creds_key[0]], database=Creds[Creds_key[4]], user=Creds[Creds_key[2]], password=Creds[Creds_key[3]], port=Creds[Creds_key[1]])

        try:
            sql_query = sql[sql_key[0]]  #0th key
            cur = conn.cursor()
            # Execute a SQL query
            cur.execute(sql_query)

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

    def automate_function_call(self, Creds_key, sql_key, function_output):
        function_output =self.ExecuteSQL(sql_key,Creds_key)
        function_output = self.ShareOutput(function_output)

        arguments = {

        "Creds_key": Creds_key,

        "sql_key": sql_key,

        "function_output": function_output

        }

        return json.dumps(arguments)

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

    def validate_json(self, input_json):
        return True, "The JSON is valid"

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

    def get_database_info(self):
        """Function to get database and table information using sql queries

        Returns:
            dict: database info
        """
        try:
            result = self.ExecuteSQL(sql_key, Creds_key)
            self.update_history({"function":"ExecuteSQL","parameters":{"sql":"SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public';"}}, result)
        except Exception as e:
            raise e

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
        
        # Problem in extracting python code
        json_output = self.extract_outermost_dict(json_output)
        # print(json_output)
        # json_output = json.loads(json_output)
        return json_output

    def _get_cost_from_usage(self, usage):
        if self.model == "text-davinci-003":
            cost = usage["totel_tokens"] * 0.00002
        elif self.model == "gpt-3.5-turbo":
            cost = usage["total_tokens"] * 0.000002
        elif self.model == "gpt-4":
            cost = (usage["prompt_tokens"] * 0.00003) + (
                usage["completion_tokens"] * 0.00006
            )
        else:
            cost = 0
        return cost
    
    def main(self):
        steps = 0
        cost = 0
        self.get_database_info() # if results==Null => SQL executed successfully; else => fetch results
        
        messages=[{"role":"system", "content":self.system_prompt}, {"role":"user", "content":self.user_prompt}]
        functions=[]

        while True:
            response = openai.ChatCompletion.create(
                engine=self.model,
                messages=messages,
                functions=functions,
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

            python_output = self.extract_json(output_response)
            print("The generated python code: ", python_output)


            time.sleep(5)

            if python_output == '':
                print(output_response)
                break

            valid_python, output = self.validate_json(python_output)

            if not valid_python:
                self.update_history(output_response, output)
                continue
            

            if output_response.get("function_call"):
                available_functions = {

                    "automate_function_call": self.automate_function_call,

                }

                function_name = output_response["function_call"]["name"]

                fuction_to_call = available_functions[function_name]

                function_args = json.loads(output_response["function_call"]["arguments"])

                function_response = fuction_to_call(


                    Creds_key=function_args.get("Creds_key"),

                    sql_key=function_args.get("sql_key"),

                    function_output=function_args.get("function_output")

                )

                function1 = {
                    "name": "automate_function_call",
                    "description": "Automate the function calling in such a way that history is updated",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Creds_key": {
                                "type": "list",
                                "description": "The list of key values for the dictionary Creds. The values of dictionary Creds are the credentials for PostGRES. These credentials are used to connect to a PostGRES server using psycopg2 library",
                            },
                            "sql_key": {
                                "type": "string",
                                "description": "The list of key values for the dictionary sql. The values of dictionary sql contains the SQL query which is executed on PostGRES server using psycopg2 library"
                            },
                            "function_output": {
                                "type": "string",
                                "description": "The output of the function 'automate_function_call' after executing two sub-functions 'ExecuteSQL', 'ShareOutput' "
                            },
                        },
                        "required": ["Creds_key", "sql_key"]
                    }
                }


                messages.append(output_response)

                messages.append(

                    {

                        "role": "function",

                        "name": function_name,

                        "content": function_response,

                    }

                )

                functions.append(function1)


            else:
                function_response = json.loads(function_response)
                function_output = function_response['function_output']
                break    



            print("The output of Function call: ",function_output)
            
            self.update_history(output_response, function_output)

            steps += 1
            cost += self._get_cost_from_usage(response['usage'])
            if cost >= self.max_cost:
                break
            if steps >= self.max_steps:
                break
        

if __name__ == "__main__":
    input_prompt = input("Enter the input prompt: ")

    # input_prompt = "Give me a python code to add two numbers"
    max_steps = 20
    max_cost = 0.5
    model = "DIR_GPT4"
    sqlInterprert(input_prompt, max_steps, max_cost, model).main()