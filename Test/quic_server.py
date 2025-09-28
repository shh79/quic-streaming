import os
import asyncio
import argparse
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
from aioquic.asyncio.protocol import QuicConnectionProtocol

class VideoStreamHandler(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.video_files = {
            b'sample_240p.mp4': open('videos/sample_240p.mp4', 'rb'),
            b'sample_480p.mp4': open('videos/sample_480p.mp4', 'rb'),
            b'sample_720p.mp4': open('videos/sample_720p.mp4', 'rb'),
            b'sample_1080p.mp4': open('videos/sample_1080p.mp4', 'rb')
        }
        self.chunk_size = 1024 * 16  # 16KB chunks

    async def handle_stream_data(self, stream_id, data):
        if data.startswith(b'GET '):
            filename = data[4:].strip()
            if filename in self.video_files:
                print(f"Sending {filename.decode()} to client...")
                video_file = self.video_files[filename]
                
                # Send video in chunks
                video_file.seek(0)
                chunk_count = 0
                while True:
                    chunk = video_file.read(self.chunk_size)
                    if not chunk:
                        break
                    self._quic.send_stream_data(stream_id, chunk, end_stream=False)
                    chunk_count += 1
                    
                    # Control sending rate
                    if chunk_count % 10 == 0:
                        await asyncio.sleep(0.001)
                
                self._quic.send_stream_data(stream_id, b'', end_stream=True)
                print(f"Completed sending {filename.decode()}")
            else:
                self._quic.send_stream_data(stream_id, b'404 Video Not Found', end_stream=True)

    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            asyncio.ensure_future(self.handle_stream_data(event.stream_id, event.data))

async def run_quic_server(host='10.0.0.1', port=4433, cc_algorithm='cubic'):
    configuration = QuicConfiguration(
        is_client=False,
        alpn_protocols=["video-stream"],
        max_datagram_frame_size=65536,
    )
    
    # Set congestion control
    if hasattr(configuration, 'congestion_control_algorithm'):
        configuration.congestion_control_algorithm = cc_algorithm
    
    # Load certificates
    configuration.load_cert_chain("cert.pem", "key.pem")
    
    server = await serve(
        host=host,
        port=port,
        configuration=configuration,
        create_protocol=VideoStreamHandler,
    )
    
    print(f"QUIC Server running on {host}:{port} with {cc_algorithm} congestion control")
    await asyncio.Future()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='10.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=4433, help='Server port')
    parser.add_argument('--cc', default='cubic', choices=['cubic', 'reno'], help='Congestion control algorithm')
    
    args = parser.parse_args()
    
    # Generate certificates if needed
    if not os.path.exists("cert.pem") or not os.path.exists("key.pem"):
        print("Generating self-signed certificates...")
        os.system("openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj '/CN=localhost'")
    
    asyncio.run(run_quic_server(args.host, args.port, args.cc))