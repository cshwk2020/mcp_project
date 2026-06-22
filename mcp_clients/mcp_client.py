from flask import Flask, request, jsonify
import asyncio
import aiohttp

class MCPClient:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session = None

    async def connect(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def get_tools(self):
        async with self.session.get(f"{self.server_url}/tools") as resp:
            return await resp.json()

    async def call_tool(self, tool_name: str, params: dict):
        async with self.session.post(
            f"{self.server_url}/tools/{tool_name}", json=params
        ) as resp:
            return await resp.json()

    async def read_resource(self, uri: str):
        async with self.session.get(
            f"{self.server_url}/resources", params={"uri": uri}
        ) as resp:
            return await resp.json()

    async def cleanup(self):
        if self.session:
            await self.session.close()
