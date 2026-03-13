import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    print("Connecting to MCP Server via SSE...")
    try:
        async with sse_client("http://localhost:8080/sse") as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("Connected successfully!")
                
                print("\n--- Available Tools ---")
                tools = await session.list_tools()
                for tool in tools.tools:
                    print(f"- {tool.name}: {tool.description}")
                
                print("\n--- Current Sources ---")
                try:
                    sources = await session.call_tool("list_sources_tool", {})
                    print(sources.content[0].text)
                except Exception as e:
                    print(f"Error calling list_sources_tool: {e}")

    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(main())
