# مسیر: /home/mininet/s1-quic/quic-server.py
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
from aioquic.asyncio.protocol import QuicConnectionProtocol
import ssl

class HttpServerProtocol(QuicConnectionProtocol):
    async def stream_received(self, stream_id, data, fin):
        self._quic.send_stream_data(stream_id, b'Hello over QUIC!', end_stream=True)

async def main():
    config = QuicConfiguration(is_client=False)
    config.load_cert_chain("cert.pem", "key.pem")
    await serve("0.0.0.0", 4433, configuration=config, create_protocol=HttpServerProtocol)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
