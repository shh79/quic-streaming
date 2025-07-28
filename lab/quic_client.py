import asyncio
import time
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration

async def main(server_host, server_port):
    config = QuicConfiguration(is_client=True)
    start = time.time()

    async with connect(server_host, server_port, configuration=config) as connection:
        stream_id = connection._quic.get_next_available_stream_id()
        reader, writer = await connection.create_stream()
        await writer.write_eof()

        total_bytes = 0
        while True:
            data = await reader.read(1024)
            if not data:
                break
            total_bytes += len(data)

    end = time.time()
    print(f"QUIC - Delay: {end - start:.2f}s, Bytes: {total_bytes}")

if __name__ == "__main__":
    import sys
    asyncio.run(main(sys.argv[1], int(sys.argv[2])))
