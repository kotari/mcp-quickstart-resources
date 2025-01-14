import asyncio
from typing import Optional
from contextlib import AsyncExitStack
import ollama
import uuid
import json
import logging
import logging.config
import sys

from rich import print
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt


from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env
# Configure logging
logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': True,
})
logging.basicConfig(
  level=logging.CRITICAL,
  format="%(asctime)s - %(levelname)s - %(message)s",
  stream=sys.stderr,
)

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.model = "llama3.2:3b-instruct-fp16"
        

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
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        } for tool in tools]


    async def process_query(self, query: str) -> str:
        """Process a query using Claude and available tools"""

        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        response = await self.session.list_tools()
        # available_tools = [{ 
        #     "name": tool.name,
        #     "description": tool.description,
        #     "input_schema": tool.inputSchema
        # } for tool in response.tools]

        available_tools = self.convert_to_openai_format(response.tools)
        
        # Initial Claude API call
        # response = self.anthropic.messages.create(
        #     model="claude-3-5-sonnet-20241022",
        #     max_tokens=1000,
        #     messages=messages,
        #     tools=available_tools
        # )
        # Switching to ollama
        response = ollama.chat(
            model=self.model, # model supporting chat functionality
            messages=messages,
            tools=available_tools or [],
            stream=False,
        )

        # Process response and handle tool calls
        tool_results = []
        final_text = []
        logging.debug("step 1: " + str(response))
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

                tool_args_str = json.dumps(tool_args, indent=2)
                tool_md = f"**Tool Call:** {tool_name}\n\n```json\n{tool_args_str}\n```"
                print(Panel(Markdown(tool_md), style="bold magenta", title="Tool Invocation"))

                result = await self.session.call_tool(tool_name, tool_args)
                tool_results.append({"call": tool_name, "result": result})
                # final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                data = result.model_dump()
                logging.debug(data)
                if data.get("isError"):
                    return f"function call for {tool_name} failed with arguments {tool_args}"
                else:
                    # updating messages (conversation history) with system calls
                    messages.append( {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call]
                    })
                    
                    for content in data.get("content", []):
                        if isinstance(content, dict) and content.get("type") == "text":
                            print(Panel(Markdown(content.get("text")), style="bold green", title="Raw response"))
                            messages.append({
                                "role": "tool",
                                "content": content.get("text")
                            })
                            logging.debug(json.dumps(messages, indent=2))
                            response = ollama.chat(
                                model=self.model, # model supporting chat functionality
                                messages=messages,
                                stream=True,
                                options={"num_ctx": 1024}
                            )
                            for chunk in response:
                                # print(chunk['message']['content'], end='', flush=True)
                                final_text.append(chunk.message.content)
                            
                            
                    return "".join(final_text)
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
                # query = input("\nQuery: ").strip()
                query = Prompt.ask("[bold yellow]Query> [/bold yellow]")

                if query.lower() == 'quit':
                    print(Panel("Exiting chate mode.", style="bold red"))
                    break
                    
                query_text = query if query else "[No Message]"
                print(Panel(query_text, style="bold yellow", title="You"))

                response = await self.process_query(query)
                logging.debug(response)
                print(Panel(Markdown(response), style="bold blue", title="Assistant Summary"))
                    
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
