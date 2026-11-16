#
# Created on Sun Mar 24 2024 codeskyblue
#

from __future__ import annotations

import asyncio
import functools
import logging
import re
import socket
import struct
from typing import Union, Callable, overload

logger = logging.getLogger(__name__)

# Tests set a count here to make the mock server kill the connection instead of
# answering a command, simulating an adb server restarted by another process.
# The count is decremented per dropped connection, so it can be set to 1 for a
# single recoverable reset or to a larger value to verify retries are bounded.
RESET_COUNTERS: dict[str, int] = {}


def reset_once(command: str) -> bool:
    remaining = RESET_COUNTERS.get(command, 0)
    if remaining <= 0:
        return False
    RESET_COUNTERS[command] = remaining - 1
    return True


def abort_connection(writer: asyncio.StreamWriter) -> None:
    """Drop the peer with a TCP RST, like a killed adb server would."""
    sock = writer.get_extra_info("socket")
    if sock is not None:
        try:
            sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
            )
        except OSError:
            pass
    writer.transport.abort()


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


# mDNS state shared with tests. host:mdns:services replies with MDNS_SERVICES
# (raw TAB separated lines) unless MDNS_ERROR is set; host:connect replies with
# MDNS_CONNECT[target], defaulting to a successful "connected to" response, and
# records every requested target in MDNS_CONNECTED.
MDNS_SERVICES: list[str] = []
MDNS_ERROR = ""
MDNS_CONNECT: dict[str, str] = {}
MDNS_CONNECTED: list[str] = []


def reset_mdns_state():
    MDNS_SERVICES.clear()
    MDNS_CONNECT.clear()
    MDNS_CONNECTED.clear()
    global MDNS_ERROR
    MDNS_ERROR = ""


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
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except (ConnectionError, OSError):
            pass

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

@register_command("host:track-devices")
async def host_track_devices(ctx: Context):
    await ctx.send(b"OKAY")
    ctx.server.track_attempts += 1
    if ctx.server.track_attempts == 1:
        # Reset after the first block so the client has to replay the whole
        # host:track-devices request on a new connection.
        await ctx.send(encode_string("dummydevice\tdevice\n"))
        abort_connection(ctx.writer)
        return
    # adb sends the complete device list on every change, so a newly attached
    # device arrives in the same block as the existing one.
    await ctx.send(encode_string("dummydevice\tdevice\notherdevice\tdevice\n"))
    try:
        while await ctx.recv(1024):
            pass
    except (ConnectionError, OSError):
        pass

@register_command(re.compile("host-serial:[0-9]*:features.*"))
async def host_serial_features(ctx: Context):
    await ctx.send(b"OKAY")
    await ctx.send(encode_string("shell_v2,fake_feature"))


@register_command("host:mdns:services")
async def host_mdns_services(ctx: Context):
    await ctx.send(b"OKAY")
    if MDNS_ERROR:
        await ctx.send(encode_string(MDNS_ERROR))
        return
    await ctx.send(encode_string("".join(line + "\n" for line in MDNS_SERVICES)))


@register_command(re.compile("host:connect:.*"))
async def host_connect(ctx: Context):
    target = ctx.command.split(":", 2)[2]
    MDNS_CONNECTED.append(target)
    await ctx.send(b"OKAY")
    await ctx.send(encode_string(MDNS_CONNECT.get(target, "connected to " + target)))


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


def _make_png(width: int = 3, height: int = 2) -> bytes:
    import io
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


SCREENCAP_PNG_SIZE = (3, 2)
SCREENCAP_PNG = _make_png(*SCREENCAP_PNG_SIZE)

# Newer devices write this warning to stdout (unless -d is given) before the
# png itself, which is what broke PIL on multi-display emulators.
SCREENCAP_WARNING = (
    b"[Warning] Multiple displays were found, but no display id was specified! "
    b"Defaulting to the first display found, however this default is not "
    b"guaranteed to be consistent across captures. A display id should be specified.\n"
    b"A display ID can be specified with the [-d display-id] option.\n"
    b'See "dumpsys SurfaceFlinger --display-id" for valid display IDs.\n'
)

# Payloads served by the exec: service, keyed by the command adb sends.
# "raw-bytes" contains LF and NUL bytes: a pty would rewrite them, exec: must
# return them unchanged.
EXEC_OUTPUTS = {
    "screencap -p": SCREENCAP_WARNING + SCREENCAP_PNG,
    "raw-bytes": b"line1\nline2\r\n\x00\x01\xff",
    "empty": b"",
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
    if reset_once(cmd):
        abort_connection(ctx.writer)
        return
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
        if shell_cmd == "reset-after-output":
            # Reset while the client is reading the stream. Regression test for
            # a reconnect that used to block forever waiting for a reply.
            await ctx.send(b"partial output")
            abort_connection(ctx.writer)
            return
        if shell_cmd == "hang":
            # Keep the service open without sending anything so the client has
            # to rely on its configured socket timeout.
            await ctx.recv(1024)
            return
        if shell_cmd in SHELL_OUTPUTS:
            await ctx.send((SHELL_OUTPUTS[shell_cmd].rstrip() + "\n").encode())
        elif shell_cmd in SHELL_DEBUGS:
            SHELL_DEBUGS[shell_cmd]()
            await ctx.send(b"debug command executed")
        else:
            await ctx.send(b"unknown command")
    elif cmd.startswith("exec:"):
        exec_cmd = cmd.split(":", 1)[1]
        payload = EXEC_OUTPUTS.get(exec_cmd)
        if payload is None:
            # An adb server without exec-out support fails before OKAY, which
            # is what makes adbutils fall back to screencap + pull.
            await ctx.send(b"FAIL")
            await ctx.send(encode("unknown service: exec"))
            return
        await ctx.send(b"OKAY")
        if payload:
            await ctx.send(payload)
    elif cmd.startswith("sync:"):
        await ctx.send(b"OKAY")
        # Consume the {COMMAND}{LittleEndianPathLength}{Path} request and drop
        # the connection, as a restarted adb server would.
        header = await ctx.recv(8)
        if len(header) == 8:
            path_len = int.from_bytes(header[4:8], "little")
            await ctx.recv(path_len)
        abort_connection(ctx.writer)
        return
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
        if reset_once(command):
            abort_connection(writer)
            return
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
        self.track_attempts = 0
    
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
