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

    def __init__(self, model, sql):
        self.model = model
        self.sql=sql
        self.user_prompt_exe = open('config/user_prompt_exe.txt', 'r').read()
        self.system_prompt_exe = open('config/system_prompt_exe.txt', 'r').read()

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
    
    def _get_cost_from_usage(self, usage):
        if self.model == "DIR_ChatBot":
            cost = usage["totel_tokens"] * 0.00002
        elif self.model == "DIR_ChatBot_FC":
            cost = usage["total_tokens"] * 0.000002
        elif self.model == "DIR_GPT4":
            cost = (usage["prompt_tokens"] * 0.00003) + (
                usage["completion_tokens"] * 0.00006
            )
        else:
            cost = 0
        return cost

    def costing_execution(self, response, cost):
        cost += self._get_cost_from_usage(response['usage'])
        return cost
        

    def main(self):
        cost = 0
        messages=[{"role":"system", "content":self.system_prompt_exe}, {"role":"user", "content":self.user_prompt_exe}]

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
                            "costing_execution": {
                                "name": "costing_execution",
                                "description": "Get cost of the execution",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "response": {
                                            "type": "string",
                                            "description": "The output of API call",
                                        },
                                          "cost": {
                                            "type": "integer",
                                            "description": "The cost for the API call",
                                        },
                                    },
                                    "required": ["cost"],
                                }
                            }
                        }, 
                        "required": ["function_call"],
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
        # print(output_response)

        # Costing
        cost=self.costing_execution(response, cost)

        if output_response.get("function_call"):
            available_functions = {

                "function_call": self.function_call,
                "costing_execution": self.costing_execution,

            }
            functions_list=json.loads(output_response["function_call"]["arguments"])
            functions = list(functions_list.keys())
            arguments = list(functions_list.values())
            n=len(functions)

            for i in range(0,n):
                function_name = functions[i]

                fuction_to_call = available_functions[function_name]

                function_args = arguments[i]

                
                if (function_name=='function_call'):

                    function_response = fuction_to_call(

                        sql=self.sql,

                        function_output=function_args.get("function_output")

                    )

                else:
                    function_response = fuction_to_call(

                        cost=function_args.get("cost"),

                        response=response

                    )


                # print('function_response: ', function_response)

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

            return output, cost


if __name__ == "__main__":
    
    model = "DIR_ChatBot_FC"
    
    sql="SELECT * from Employees;"

    output=Execute_sql(model, sql).main()
    print(output)  


