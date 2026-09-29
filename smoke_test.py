import argparse
import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parent
TOOL_NAME = "query_foundry"


async def run_smoke_test(question: str) -> int:
    missing = [
        name
        for name in ("FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_AGENT_NAME")
        if not os.getenv(name)
    ]
    if missing:
        print(
            "Missing required environment variables: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    server = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "mcp_server.py")],
        cwd=str(ROOT),
        env=os.environ.copy(),
    )

    try:
        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                if TOOL_NAME not in {tool.name for tool in tools.tools}:
                    print(f"MCP tool '{TOOL_NAME}' was not discovered.", file=sys.stderr)
                    return 1

                result = await session.call_tool(
                    TOOL_NAME,
                    arguments={"question": question},
                    read_timeout_seconds=120,
                )
                output = "\n".join(
                    content.text
                    for content in result.content
                    if getattr(content, "text", None)
                ).strip()
                if getattr(result, "isError", getattr(result, "is_error", False)):
                    print(output or "The MCP tool returned an error.", file=sys.stderr)
                    return 1
                if not output:
                    print("The MCP tool returned no text output.", file=sys.stderr)
                    return 1

                print(output)
                return 0
    except Exception as exc:
        print(f"MCP smoke test failed ({type(exc).__name__}).", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the local MCP server and query its configured Foundry agent."
    )
    parser.add_argument(
        "--question",
        default="What information is available in your knowledge base?",
        help="Question to send to the configured Foundry agent.",
    )
    args = parser.parse_args()
    return asyncio.run(run_smoke_test(args.question))


if __name__ == "__main__":
    raise SystemExit(main())