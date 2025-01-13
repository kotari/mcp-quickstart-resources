import asyncio
from typing import Optional
from contextlib import AsyncExitStack
import ollama
import uuid


from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server
        
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    def convert_to_openai_format(self, tools):
        """Convert tools to OpenAI format"""
        return [{
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {})   
            }
        } for tool in tools]
    

    def get_system_prompt(self):
        prompt = """
You are a weather agent interacting with users to extract the intent and making an API call to national weather service.\n\n
National weather service expects the query parameters in a predefined format to provide results. \n\n

Predefined format expects two char state code or latitude and longitude for a given US city. \n
You are responsible for translating the user intent to either \n
```
{
    "state": f{state_code} #This will be a 2 char US state code
}
```\n
or
```
{
    "latitude": f"{latitude}",
    "longitude": f"{longitude}"
}
```\n
for function calling. \n



If you are not able get the intent from user input ask them for further clarification or you can respond with \n
'I am  not able to interpret the intent of your request'\n\n
"""
        return prompt

    async def process_query(self, query: str) -> str:
        """Process a query using Claude and available tools"""

        messages = [
            {
                "role": "system",
                "content": self.get_system_prompt()
            },
            {
                "role": "user",
                "content": query
            }
        ]

        response = await self.session.list_tools()
        available_tools = [{ 
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

        available_tools = self.convert_to_openai_format(available_tools)

        # Initial Claude API call
        # response = self.anthropic.messages.create(
        #     model="claude-3-5-sonnet-20241022",
        #     max_tokens=1000,
        #     messages=messages,
        #     tools=available_tools
        # )
        # Switching to ollama
        response = ollama.chat(
            model="llama3.2:3b-instruct-fp16", # model supporting chat functionality
            messages=messages,
            tools=available_tools or [],
            stream=False,
        )

        # Process response and handle tool calls
        tool_results = []
        final_text = []
        # print("step 1:", str(response))
        message = response.message
        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tool in message.tool_calls:
                tool_calls.append({
                    "id": str(uuid.uuid4()),
                    "type": "function",
                    "function": {
                        "name": tool.function.name,
                        "arguments": tool.function.arguments,
                    }
                })

        if tool_calls:
            for tool_call in tool_calls:
                if hasattr(tool_call, "function"):
                    tool_name = getattr(tool_call.function, "name", "no tool found")
                    tool_args = getattr(tool_call.function, "arguments", {})
                elif isinstance(tool_call, dict) and "function" in tool_call:
                    fn_info = tool_call["function"]
                    tool_name = fn_info.get("name", "no tool found")
                    tool_args = fn_info.get("arguments", {})
                else:
                    tool_name = "no tool found"
                    tool_args = {}

                result = await self.session.call_tool(tool_name, tool_args)
                tool_results.append({"call": tool_name, "result": result})
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                data = result.model_dump()
                # print("\nfunction calling response:\n")
                # print(data)
                if data.get("isError"):
                    return f"function call for {tool_name} failed with arguments {tool_args}"
                else:
                    messages = messages[1:]
                    for content in data.get("content", []):
                        if isinstance(content, dict) and content.get("type") == "text":
                            messages.append({
                                "role": "tool",
                                "content": content.get("text")
                            })
                            # print(messages)
                            response = ollama.chat(
                                model="llama3.2:3b-instruct-fp16", # model supporting chat functionality
                                messages=messages,
                                stream=False,
                                options={"num_ctx": 1024}
                            )
                            # return content.get("text")
                            # print("\nsummary:\n")
                            # print(response)
                            final_text.append(response.message.content)
                            
                    return "\n".join(final_text)
                # tool_results.append({"call": tool_name, "result": result})
                # final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

        # for content in response.content:
        #     if content.type == 'text':
        #         final_text.append(content.text)
        #     elif content.type == 'tool_use':
        #         tool_name = content.name
        #         tool_args = content.input
                
        #         # Execute tool call
        #         result = await self.session.call_tool(tool_name, tool_args)
        #         tool_results.append({"call": tool_name, "result": result})
        #         final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

        #         # Continue conversation with tool results
        #         if hasattr(content, 'text') and content.text:
        #             messages.append({
        #               "role": "assistant",
        #               "content": content.text
        #             })
        #         messages.append({
        #             "role": "user", 
        #             "content": result.content
        #         })

        #         # Get next response from Claude
        #         response = self.anthropic.messages.create(
        #             model="claude-3-5-sonnet-20241022",
        #             max_tokens=1000,
        #             messages=messages,
        #         )

        #         final_text.append(response.content[0].text)

        # return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                    
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)
        
    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    import sys
    asyncio.run(main())
