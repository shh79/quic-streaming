from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
from aioquic.asyncio.protocol import QuicConnectionProtocol
import asyncio

class VideoStreamServer(QuicConnectionProtocol):
    async def stream_handler(self, stream_id: int, stream_reader, stream_writer):
        print(f"Client connected on stream {stream_id}")
        with open("test_video.mp4", "rb") as f:
            data = f.read()
            stream_writer.write(data)
            await stream_writer.drain()
            stream_writer.write_eof()

async def main():
    config = QuicConfiguration(is_client=False)
    config.load_cert_chain("cert.pem", "key.pem")
    await serve("0.0.0.0", 4433, configuration=config,
                create_protocol=VideoStreamServer)

if __name__ == "__main__":
    asyncio.run(main())
