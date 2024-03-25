#
# Created on Sun Mar 24 2024 codeskyblue
#

from __future__ import annotations

import asyncio
import functools
import logging
from typing import overload

logger = logging.getLogger(__name__)



@overload
def encode(data: str) -> bytes:
    ...

@overload
def encode(data: bytes) -> bytes:
    ...

@overload
def encode(data: int) -> bytes:
    ...


def encode(data):
    if isinstance(data, bytes):
        return encode_bytes(data)
    if isinstance(data, int):
        return encode_number(data)
    if isinstance(data, str):
        return encode_string(data)
    raise ValueError("data must be bytes or int")


def encode_number(n: int) -> bytes:
    body = "{:04x}".format(n)
    return encode_bytes(body.encode())

def encode_string(s: str, encoding: str = 'utf-8') -> bytes:
    return encode_bytes(s.encode(encoding))

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
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, server: "AdbServer" = None):
        self.reader = reader
        self.writer = writer
        self.server = server
            
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


@register_command("host:kill")
async def host_kill(ctx: Context):
    await ctx.send(b"OKAY")
    await ctx.close()
    await ctx.server.stop()
    # os.kill(os.getpid(), signal.SIGINT)


async def handle_command(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, server: "AdbServer"):
    try:
         # Receive the command from the client
        addr = writer.get_extra_info('peername')
        logger.info(f"Connection from %s", addr)
        cmd_length = int((await reader.readexactly(4)).decode(), 16)
        command = (await reader.read(cmd_length)).decode()
        logger.info("recv command: %s", command)
        if command not in COMMANDS:
            writer.write(b"FAIL")
            writer.write(encode(f"Unknown command: {command}"))
            await writer.drain()
            writer.close()
            return
        ctx = Context(reader, writer, server)
        await COMMANDS[command](ctx)
        await ctx.close()
    except asyncio.IncompleteReadError:
        pass



class AdbServer:
    def __init__(self, port: int = 7305, host: str = '127.0.0.1'):
        self.port = port
        self.host = host
        self.server = None
    
    async def start(self):
        _handle = functools.partial(handle_command, server=self)
        self.server = await asyncio.start_server(_handle, self.host, self.port)
        addr = self.server.sockets[0].getsockname()
        print(f'ADB server listening on {addr}')

        async with self.server:
            try:
                # Keep running the server
                await self.server.serve_forever()
            except asyncio.CancelledError:
                pass
    
    async def stop(self):
        self.server.close()
        await self.server.wait_closed()



async def adb_server():
    host = '127.0.0.1'
    port = 7305
    await AdbServer(port, host).start()


def run_adb_server():
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(adb_server())


if __name__ == '__main__':
    run_adb_server()