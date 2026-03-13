from src.server import mcp
from src.config import settings


def main():
    if settings.MCP_TRANSPORT == "sse":
        mcp.run(transport="sse", port=settings.MCP_PORT)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
