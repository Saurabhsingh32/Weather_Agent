import asyncio

from fastmcp import Client


async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:

        result = await client.call_tool(
            "update_note",
            {
                "note_id": "b77ecb65-c7a1-4f06-88a0-89061dfe018a",
                "payload": {
                    "title": "Updated through MCP"
                }
            }
        )

        print(result)


if __name__ == "__main__":
    asyncio.run(main())