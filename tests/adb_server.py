#
# Created on Sun Mar 24 2024 codeskyblue
#

from __future__ import annotations

import asyncio
import logging
from typing import overload

logger = logging.getLogger(__name__)



@overload
def encode(data: str) -> bytes:
    ...

@overload
def encode(data: bytes) -> bytes:
    ...

def encode(data):
    if isinstance(data, bytes):
        return encode_bytes(data)
    if isinstance(data, int):
        return encode_number(data)
    raise ValueError("data must be bytes or int")


def encode_number(n: int) -> bytes:
    body = "{:04x}".format(n)
    return encode_bytes(body.encode())


def encode_bytes(s: bytes) -> bytes:
    header = "{:04x}".format(len(s)).encode()
    return header + s


COMMANDS: dict[str, callable] = {}

def register_command(name: str):
    def wrapper(func):
        COMMANDS[name] = func
        return func
    return wrapper


class Context:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
            
    async def send(self, data: bytes):
        self.writer.write(data)
        await self.writer.drain()

    async def recv(self, length: int) -> bytes:
        return await self.reader.read(length)

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()


@register_command("host:version")
async def host_version(ctx: Context):
    await ctx.send(b"OKAY")
    await ctx.send(encode_number(1234))



async def handle_command(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        await _handle_command(reader, writer)
    except asyncio.IncompleteReadError:
        pass


async def _handle_command(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    # Receive the command from the client
    addr = writer.get_extra_info('peername')
    logger.info(f"Connection from %s", addr)
    cmd_length_bytes = await reader.readexactly(4)
    cmd_length = int(cmd_length_bytes.decode(), 16)
    logger.debug("cmd_length: %d", cmd_length)
    command = (await reader.read(cmd_length)).decode()
    logger.info("recv command: %s", command)
    if command not in COMMANDS:
        writer.write(b"FAIL")
        await writer.drain()
        writer.close()
        return
    ctx = Context(reader, writer)
    await COMMANDS[command](ctx)
    await ctx.close()



class AdbServer:
    def __init__(self, port: int = 7305, host: str = '127.0.0.1'):
        self.port = port
        self.host = host
    
    async def start(self):
        server = await asyncio.start_server(handle_command, self.host, self.port)# Print server info
        addr = server.sockets[0].getsockname()
        print(f'ADB server listening on {addr}')

        async with server:
            # Keep running the server
            await server.serve_forever()


async def adb_server():
    host = '127.0.0.1'
    port = 7305
    await AdbServer(port, host).start()


def run_adb_server():
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(adb_server())


if __name__ == '__main__':
    run_adb_server()