from config.envs import OPENAI_API_TYPE, OPENAI_BASE_URL, OPENAI_API_KEY, TEMPERATURE, STOP, MAX_TOKENS, TOP_P, FREQUENCY_PENALTY, PRESENCE_PENALTY, N_RESP, TIMEOUT, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
import psycopg2
import json
import openai


if OPENAI_API_TYPE == 'azure':
    openai.api_base = OPENAI_BASE_URL
    openai.api_key = OPENAI_API_KEY
    openai.api_type = OPENAI_API_TYPE
    openai.api_version = "2023-07-01-preview"
else:
    openai.api_key = OPENAI_API_KEY


class Execute_sql():

    def __init__(self, model):
        self.model = model
        self.user_prompt1 = open('config/user_prompt1.txt', 'r').read()
        self.system_prompt1 = open('config/system_prompt1.txt', 'r').read()

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

    def function_call(self, sql, function_output):
        function_output =self.ExecuteSQL(sql)
        function_output = self.ShareOutput(function_output)

        arguments = {

            "sql_key": sql,

            "function_output": function_output

        }

        return json.dumps(arguments)

    def main(self, sql):

        messages=[{"role":"system", "content":self.system_prompt1}, {"role":"user", "content":self.user_prompt1}]

        functions=[
            
                {
                    "name": "multi_Func",
                    "description": "Call two functions in one call",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "function_call": {
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
                            },
                            # "second_function": {
                            #     "name": "get_Events",
                            #     "description": "Get events for the location at specified date",
                            #     "parameters": {
                            #         "type": "object",
                            #         "properties": {
                            #             "location": {
                            #                 "type": "string",
                            #                 "description": "The city and state, e.g. San Francisco, CA",
                            #             },
                            #             "date": {
                            #                 "type": "string",
                            #                 "description": "The date of the event, e.g. 2021-01-01."
                            #             }
                            #         },
                            #         "required": ["location", "date"],
                            #     }
                            # }
                        }, "required": ["function_call"],
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
        print(output_response)

        if output_response.get("function_call"):
            available_functions = {

                "function_call": self.function_call,

            }
            functions_list=json.loads(output_response["function_call"]["arguments"])
            functions = list(functions_list.keys())
            arguments = list(functions_list.values())
            n=len(functions)
            for i in range(n):
                function_name = functions[i]

                fuction_to_call = available_functions[function_name]

                function_args = arguments[i]

                function_response = fuction_to_call(

                    sql=sql,

                    function_output=function_args.get("function_output")

                )

                print('function_response: ', function_response)

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

            print( output)


if __name__ == "__main__":
    model = "DIR_ChatBot_FC"
    
    sql="SELECT * from Employees;"
    Execute_sql(model).main(sql)       


