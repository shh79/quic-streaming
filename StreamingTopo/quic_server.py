# Save this as /tmp/quic_server.py on host s1
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
import asyncio

class VideoServerProtocol:
    def __init__(self):
        self.streams = {}

    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            stream_id = event.stream_id
            data = b"Video stream response: (fake video chunk)\n"
            self.streams[stream_id].send_stream_data(data, end_stream=True)

async def main():
    configuration = QuicConfiguration(is_client=False)
    configuration.load_cert_chain(certfile="../cert.pem", keyfile="../key.pem")

    await serve(
        host="10.0.0.1",
        port=4433,
        configuration=configuration,
        create_protocol=VideoServerProtocol
    )

    print("Quic server is setup")

if __name__ == "__main__":
    asyncio.run(main())
