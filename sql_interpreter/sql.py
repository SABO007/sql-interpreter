import datetime
import ast
import openai
import psycopg2
import re
import json
from tabulate import tabulate
from prettytable import PrettyTable 
from config.envs import OPENAI_API_TYPE, OPENAI_BASE_URL, OPENAI_API_KEY, TEMPERATURE, STOP, MAX_TOKENS, TOP_P, FREQUENCY_PENALTY, PRESENCE_PENALTY, N_RESP, TIMEOUT, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT)

# setup openai
if OPENAI_API_TYPE == 'azure':
    openai.api_base = OPENAI_BASE_URL
    openai.api_key = OPENAI_API_KEY
    openai.api_type = OPENAI_API_TYPE
    openai.api_version = "2023-07-01-preview"
else:
    openai.api_key = OPENAI_API_KEY

class SQL_Interpreter():
    def __init__(self, input_prompt, max_steps, max_cost, model) -> None:
        self.input_prompt = input_prompt
        self.max_steps = max_steps
        self.max_cost = max_cost
        self.model = model
        self.system_prompt = open('config/system_prompt1.txt', 'r').read()
        self.user_prompt = open('config/user_prompt.txt', 'r').read()
        self.user_prompt = self.user_prompt.replace('<input>', self.input_prompt)

    
    def ExecuteSQL(self, sql) -> str:
        """Function to execute SQL query

        Args:
            sql (str): sql query to execute

        Returns:
            str: output of sql query
        """
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT)

        try:
            cur = conn.cursor()
            # Execute a SQL query
            cur.execute(sql)

            # Fetch the results
            results = cur.fetchall()

            # Close the cursor and connection
            cur.close()
            if not results:
                return "PostgresSQL Query executed Successfully"
            else:
                headers = [desc[0] for desc in cur.description]
                rows = [list(row) for row in results]
                table = tabulate(rows, headers=headers, tablefmt="pipe")
                return f"```\n{table}\n```"

        except Exception as e:
            return f"There is some error in SQL query: {str(e)}"
    

    def validate_json(self, input_json):
        return True, "The JSON is valid"


    def get_database_info(self, system_prompt):
        """Function to get database and table information using sql queries

        Returns:
            dict: database info
        """
        try:
            result = self.ExecuteSQL("SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public';")
            system_prompt = system_prompt.replace('<table_info>', f"{result}")
            return system_prompt
        except Exception as e:
            raise e


    def _get_cost_from_usage(self, usage):
        if self.model == "DIR_ChatBot":
            cost = usage["total_tokens"] * 0.00002
        elif self.model == "DIR_ChatBot_FC":
            cost = usage["total_tokens"] * 0.000002
        elif self.model == "DIR_GPT4":
            cost = (usage["prompt_tokens"] * 0.00003) + (
                usage["completion_tokens"] * 0.00006
            )
        else:
            cost = 0
        return cost
    
    def main(self):
        steps = 0 
        cost = 0 
        ExecuteCount=0
        # self.system_prompt=self.get_database_info(self.system_prompt)
        messages=[{"role":"system", "content":self.system_prompt}, {"role":"user", "content":self.user_prompt}]
        functions=[
             {
                    "name": "ExecuteSQL",
                    "description": "The function which runs the SQL query on Postgres server and give back output",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "The SQL query to be executed on Postgres server",
                                },
                            },
                            "required": ["sql"]
                    }
            }
        ]


        while True:
            response = openai.ChatCompletion.create(
                engine=self.model,
                messages=messages,
                temperature=TEMPERATURE,
                functions=functions,
                max_tokens=MAX_TOKENS,
                top_p=TOP_P,
                frequency_penalty=FREQUENCY_PENALTY,
                presence_penalty=PRESENCE_PENALTY,
                stop=STOP,
                timeout=TIMEOUT,
                n=N_RESP
            )
            
            output_response = response['choices'][0]['message']
            if "function_call" in output_response:
                try:
                    json_output = json.loads(output_response['function_call']['arguments'])
                    if json_output['sql']:
                        sql=json_output['sql']
                        print("Generated SQL Query: ", sql)
                        output=self.ExecuteSQL(sql)

                    elif json_output['query']:
                        sql=json_output['query']
                        print("Generated SQL Query: ", sql)
                        output=self.ExecuteSQL(sql)

                    steps += 1
                    cost += self._get_cost_from_usage(response['usage'])

                    if (json_output['sql'] == "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public';"):
                        messages.append(
                            {
                                "role": "assistant",

                                "content": output
                            }
                        )
            
                except:
                    messages.append(
                        {
                            "role": "assistant",

                            "content": output
                        }
                    )
                    continue
                
            else:
                print(output_response['content'])
                messages.append(
                        {
                            "role": "assistant",

                            "content": output_response['content']
                        }
                    )
                output=output_response['content']
                
            print("---------------")
            print("---------------")
            print(f"Iteration {ExecuteCount+1}")
            print("---------------")
            print(f'Overall Cost for Iteration {ExecuteCount+1}: ', cost)
            print("--------------------------------------------")

            ExecuteCount+=1

            if (ExecuteCount>3):
                print(f"The output after executing the SQL Query \"{sql}\": ") 
                print(output)
                print("--------------------------------------------")
                break

            if cost >= self.max_cost:
                break
            if steps >= self.max_steps:     
                break
        

if __name__ == "__main__":

    while True:
        input_prompt = input("Enter the input prompt: ")
        if input_prompt:
            max_steps = 20
            max_cost = 0.5
            model = "DIR_ChatBot_FC"
            SQL_Interpreter(input_prompt, max_steps, max_cost, model).main()
            break
        else:
            print("Input cannot be null. Please try again.")
