#
# Created on Sun Mar 24 2024 codeskyblue
#

from __future__ import annotations

import asyncio
import functools
import logging
import re
import struct
from typing import Union, Callable, overload

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



COMMANDS: dict[Union[str, re.Pattern], Callable] = {}

def register_command(name: Union[str, re.Pattern]):
    def wrapper(func):
        COMMANDS[name] = func
        return func
    return wrapper


class Context:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, server: "AdbServer" = None, command: str = None):
        self.reader = reader
        self.writer = writer
        self.server = server
        self.command = command
            
    async def send(self, data: bytes):
        self.writer.write(data)
        await self.writer.drain()

    async def recv(self, length: int) -> bytes:
        return await self.reader.read(length)

    async def recv_string_block(self) -> str:
        length = int((await self.recv(4)).decode(), 16)
        return (await self.recv(length)).decode()
    
    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()

    async def send_shell_v2(self, stream_id: int, payload: bytes):
        header = bytes([stream_id]) + len(payload).to_bytes(4, "little")
        await self.send(header + payload)


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

@register_command("host:list-forward")
async def host_list_forward(ctx: Context):
    await ctx.send(b"OKAY")
    await ctx.send(encode_string("123456 tcp:1234 tcp:4321"))

@register_command(re.compile("host-serial:[0-9]*:features.*"))
async def host_serial_features(ctx: Context):
    await ctx.send(b"OKAY")
    await ctx.send(encode_string("shell_v2,fake_feature"))


def enable_devices():
    @register_command("host:devices")
    async def host_devices(ctx: Context):
        await ctx.send(b"OKAY")
        await ctx.send(encode_string("dummydevice\tdevice\n"))

    @register_command("host:devices-l")
    async def host_devices_extended(ctx: Context):
        await ctx.send(b"OKAY")
        await ctx.send(encode_string("dummydevice\tdevice product:test_emu model:test_model device:test_device\n"))
        

def invalidate_devices():
    @register_command("host:devices")
    async def host_devices(ctx: Context):
        await ctx.send(b"OKAY")
        await ctx.send(encode_string("dummydevice"))
        
    @register_command("host:devices-l")
    async def host_devices_extended(ctx: Context):
        """"""
        await ctx.send(b"OKAY")
        await ctx.send(encode_string("dummydevice"))

SHELL_DEBUGS = {
    "enable-devices": enable_devices,
    "invalidate-devices": invalidate_devices
}

SHELL_OUTPUTS = {
    "pwd": "/",
    "pwd; echo X4EXIT:$?": "/\nX4EXIT:0"
}

SHELL_V2_COMMANDS = {
    "v2-stdout-only": {
        "stdout": b"this is stdout\n",
        "stderr": b"",
        "exit": 0,
    },
    "v2-stdout-stderr": {
        "stdout": b"this is stdout\n",
        "stderr": b"this is stderr\n",
        "exit": 1,
    },
}


def send_shell_v2(writer, stream_id: int, payload: bytes):
    length = struct.pack(">I", len(payload))
    return writer.send(bytes([stream_id]) + length + payload)

@register_command(re.compile("host:tport:serial:.*"))
async def host_tport_serial(ctx: Context):
    serial = ctx.command.split(":")[-1]
    if serial == "not-found":
        await ctx.send(b"FAIL")
        await ctx.send(encode("device not found"))
        return
    else:
        await ctx.send(b"OKAY")
        await ctx.send(b"\x00\x00\x00\x00\x00\x00\x00\x00")

    cmd = await ctx.recv_string_block()
    logger.info("recv shell cmd: %s", cmd)
    if cmd.startswith("shell,v2:"):
        await ctx.send(b"OKAY")
        shell_cmd = cmd.split(":", 1)[1]

        result = SHELL_V2_COMMANDS.get(shell_cmd)
        if result is None:
            await ctx.send_shell_v2(2, b"unknown shell_v2 command\n")
            await ctx.send_shell_v2(3, b"\x01")
            return

        if result["stdout"]:
            await ctx.send_shell_v2(1, result["stdout"])
        if result["stderr"]:
            await ctx.send_shell_v2(2, result["stderr"])
        await ctx.send_shell_v2(3, bytes([result["exit"]]))

    elif cmd.startswith("shell:"):
        await ctx.send(b"OKAY")
        shell_cmd = cmd.split(":", 1)[1]
        if shell_cmd in SHELL_OUTPUTS:
            await ctx.send((SHELL_OUTPUTS[shell_cmd].rstrip() + "\n").encode())
        elif shell_cmd in SHELL_DEBUGS:
            SHELL_DEBUGS[shell_cmd]()
            await ctx.send(b"debug command executed")
        else:
            await ctx.send(b"unknown command")
    else:
        await ctx.send(b"FAIL")
        await ctx.send(encode("unsupported command"))


async def handle_command(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, server: "AdbServer"):
    try:
         # Receive the command from the client
        addr = writer.get_extra_info('peername')
        logger.info(f"Connection from %s", addr)
        cmd_length = int((await reader.readexactly(4)).decode(), 16)
        command = (await reader.read(cmd_length)).decode()
        logger.info("recv command: %s", command)
        command_handler: callable = None
        command_keys = list(COMMANDS.keys())
        logger.debug("command_keys: %s", command_keys)
        for key in command_keys:
            if isinstance(key, str) and key == command:
                command_handler = COMMANDS[key]
                break
            elif isinstance(key, re.Pattern) and key.match(command):
                command_handler = COMMANDS[key]
                break

        logger.debug("command_handler: %s", command_handler)
        if command_handler is None:
            writer.write(b"FAIL")
            writer.write(encode(f"Unknown command: {command}"))
            await writer.drain()
            writer.close()
            return
        ctx = Context(reader, writer, server, command)
        await command_handler(ctx)
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
    try:
        import logzero
        logzero.setup_logger(__name__)
    except ImportError:
        pass
    
    try:
        asyncio.run(adb_server())
    except:
        logger.exception("Error in adb_server")


if __name__ == '__main__':
    run_adb_server()
