#
# Created on Sun Mar 24 2024 codeskyblue
#
import asyncio
import logging

logger = logging.getLogger(__name__)

async def handle_command(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        await _handle_command(reader, writer)
    except asyncio.IncompleteReadError:
        pass


async def _handle_command(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    # Receive the command from the client
    addr = writer.get_extra_info('peername')
    logger.debug(f"Connection from %s", addr)
    cmd_length_bytes = await reader.readexactly(4)
    cmd_length = int(cmd_length_bytes.decode(), 16)
    logger.debug("cmd_length: %d", cmd_length)
    command = (await reader.read(cmd_length)).decode()
    logger.info("recv command: %s", command)
    if command == "host:version":
        writer.write(b"OKAY")
        writer.write(encode_number(1234))
    await writer.drain()
    writer.close()


def encode_number(n: int) -> bytes:
    body = "{:04x}".format(n)
    header = "{:04x}".format(len(body))
    return (header + body).encode()


async def adb_server():
    host = '127.0.0.1'
    port = 7305

    server = await asyncio.start_server(handle_command, host, port)

    # Print server info
    addr = server.sockets[0].getsockname()
    print(f'ADB server listening on {addr}')

    async with server:
        # Keep running the server
        await server.serve_forever()


def run_adb_server():
    asyncio.run(adb_server())


if __name__ == '__main__':
    run_adb_server()