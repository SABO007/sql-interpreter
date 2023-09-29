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


class sqlInterprert():

    def __init__(self, model):
        self.model = model
        self.user_prompt = open('config/user_prompt1.txt', 'r').read()
        self.system_prompt = open('config/system_prompt1.txt', 'r').read()

    def ExecuteSQL(self, sql, Creds) -> str:
        """Function to execute SQL query

        Args:
            sql (str): sql query to execute

        Returns:
            str: output of sql query
        """
        Creds={'Host': DB_HOST, 'Port': DB_PORT, 'User': DB_USER, 'Password': DB_PASSWORD, 'Name': DB_NAME}
        sql="SELECT * from Employees;"

        conn = psycopg2.connect(host=Creds['Host'], database=Creds['Name'], user=Creds['User'], password=Creds['Password'], port=Creds['Port'])

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

    def function_call(self, sql, Creds, function_output):
        function_output =self.ExecuteSQL(sql, Creds)
        function_output = self.ShareOutput(function_output)

        arguments = {

            "sql_key": sql,

            "Creds_key": Creds,

            "function_output": function_output

        }

        return json.dumps(arguments)

    def main(self):

        messages=[{"role":"system", "content":self.system_prompt}, {"role":"user", "content":self.user_prompt}]

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
                            "Creds": {
                                "type": "string",
                                "description": "The string which consists a dictionary. The values of dictionary Creds are the credentials for PostGRES. These credentials are used to connect to a PostGRES server using psycopg2 library to run our SQL command. ",
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

                sql=function_args.get("sql"),

                Creds=function_args.get("Creds"),

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
    model = "DIR_ChatBot_FC"
    sqlInterprert(model).main()       


