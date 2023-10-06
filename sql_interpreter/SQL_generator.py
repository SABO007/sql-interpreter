import datetime
import time
import ast
import openai
import os
import math
import psycopg2
import re
import json
from config.envs import OPENAI_API_TYPE, OPENAI_BASE_URL, OPENAI_API_KEY, TEMPERATURE, STOP, MAX_TOKENS, TOP_P, FREQUENCY_PENALTY, PRESENCE_PENALTY, N_RESP, TIMEOUT, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

# Establish a connection to the PostgreSQL server
conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT)

# setup openai
if OPENAI_API_TYPE == 'azure':
    openai.api_base = OPENAI_BASE_URL
    openai.api_key = OPENAI_API_KEY
    openai.api_type = OPENAI_API_TYPE
    openai.api_version = "2023-03-15-preview"
else:
    openai.api_key = OPENAI_API_KEY

class SQL_generator():
    def __init__(self, input_prompt, model) -> None:
        self.input_prompt = input_prompt
        self.model = model
        self.system_prompt = open('config/system_prompt.txt', 'r').read()
        self.base_user_prompt = open('config/user_prompt.txt', 'r').read()
        self.system_prompt = self.system_prompt.replace('<input>', self.input_prompt)
        self.history = "Empty"
        self.user_prompt = self.base_user_prompt.replace('<history>', self.history[0])
        self.current_time = datetime.datetime.now()
        self.current_time = self.current_time.strftime("%Y-%m-%d %H:%M:%S")
        self.user_prompt = self.user_prompt.replace('<DateTime>', self.current_time)

    
    def ExecuteSQL(self, params) -> str:
        """Function to execute SQL query

        Args:
            sql (str): sql query to execute

        Returns:
            str: output of sql query
        """
        try:
            sql = params['sql']
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
            result = self.ExecuteSQL({"sql":"SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public';"})
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
        print("The first output response: ", output_response)

        json_output = self.extract_json(output_response)
        print("The first json output: ", json_output)

        SQL=json_output['parameters']['sql']
        print("The generated SQL query: ", SQL)



# class SQL_executor():

#     def __init__(self, model):
#         self.model = model
#         self.user_prompt1 = open('config/user_prompt1.txt', 'r').read()
#         self.system_prompt1 = open('config/system_prompt1.txt', 'r').read()

#     def ExecuteSQL(self, sql, Creds) -> str:
#         """Function to execute SQL query

#         Args:
#             sql (str): sql query to execute

#         Returns:
#             str: output of sql query
#         """
#         Creds={'Host': DB_HOST, 'Port': DB_PORT, 'User': DB_USER, 'Password': DB_PASSWORD, 'Name': DB_NAME}
#         sql="SELECT employeeid FROM employees;"

#         conn = psycopg2.connect(host=Creds['Host'], database=Creds['Name'], user=Creds['User'], password=Creds['Password'], port=Creds['Port'])

#         try:
#             cur = conn.cursor()
#             # Execute a SQL query
#             cur.execute(sql)

#             # Fetch the results
#             results = cur.fetchall()

#             # Close the cursor and connection
#             cur.close()
#             if results == '':
#                 return "PostgresSQL Query executed Successfully"
#             else:
#                 self.ShareOutput(results)
#                 return results
#         except Exception as e:
#             return f"There is some error in SQL query: {str(e)}"
    
#     def ShareOutput(self, output: str) -> str:
#         """Function to share output

#         Args:
#             output (str): output to share

#         Returns:
#             str: output of sharing output
#         """
#         try:
#             return output
#         except Exception as e:
#             return e

#     def function_call(self, sql, Creds, function_output):
#         function_output =self.ExecuteSQL(sql, Creds)
#         function_output = self.ShareOutput(function_output)

#         arguments = {

#             "sql_key": sql,

#             "Creds_key": Creds,

#             "function_output": function_output

#         }

#         return json.dumps(arguments)

#     def main(self):

#         messages=[{"role":"system", "content":self.system_prompt1}, {"role":"user", "content":self.user_prompt1}]

#         functions=[
#             {
#                     "name": "function_call",
#                     "description": "The function which runs the SQL query on Postgres server and give back output",
#                     "parameters": {
#                         "type": "object",
#                         "properties": {
#                             "sql": {
#                                 "type": "string",
#                                 "description": "The SQL query which is executed on PostGRES server using psycopg2 library"
#                             },
#                             "Creds": {
#                                 "type": "string",
#                                 "description": "The string which consists a dictionary. The values of dictionary Creds are the credentials for PostGRES. These credentials are used to connect to a PostGRES server using psycopg2 library to run our SQL command. ",
#                             },

#                             "function_output": {
#                                 "type": "string",
#                                 "description": "The output of the function 'automate_function_call' after executing two sub-functions 'ExecuteSQL', 'ShareOutput'. This is the output of the SQL query. "
#                             },
#                         },
#                         "required": ["function_output"]
#                     }
#                 }
#                 ]
    
#         response = openai.ChatCompletion.create(
#                 engine=self.model,
#                 messages=messages,
#                 functions=functions,
#                 temperature=TEMPERATURE,
#             )
            
#         output_response = response['choices'][0]['message']

#         if output_response.get("function_call"):
#             available_functions = {

#                 "function_call": self.function_call,

#             }

#             function_name = output_response["function_call"]["name"]

#             fuction_to_call = available_functions[function_name]

#             function_args = json.loads(output_response["function_call"]["arguments"])

#             function_response = fuction_to_call(

#                 sql=function_args.get("sql"),

#                 Creds=function_args.get("Creds"),

#                 function_output=function_args.get("function_output")

#             )

#             print('function_response: ', function_response)

#             # messages.append(output_response)

#             messages.append(

#                 {

#                     "role": "function",

#                     "name": function_name,

#                     "content": function_response,

#                 }

#             )

#             second_response = openai.ChatCompletion.create(
#                             engine=self.model,
#                             messages=messages,
#             ) 
#             output = second_response['choices'][0]['message']['content']

#             print("\n")
#             print( output)


if __name__ == "__main__":
    input_prompt = input("Enter the input prompt: ")
    # input_prompt = "How many executions were done last month?"
    model = "DIR_ChatBot_FC"
    SQL_generator(input_prompt, model).main()
    # SQL_executor(model).main()       
