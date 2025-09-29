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
        # Create videos directory if it doesn't exist
        os.makedirs('videos', exist_ok=True)
        
        # Initialize video files for THIS instance
        self.video_files = {}
        video_files = ['sample_240p.mp4', 'sample_480p.mp4', 'sample_720p.mp4', 'sample_1080p.mp4']
        
        for video_file in video_files:
            video_path = f'videos/{video_file}'
            if os.path.exists(video_path):
                try:
                    self.video_files[video_file.encode()] = open(video_path, 'rb')
                    print(f"Loaded video: {video_file}")
                except Exception as e:
                    print(f"Error opening {video_file}: {e}")
            else:
                print(f"Warning: Video file {video_file} not found at {video_path}")
        
        self.chunk_size = 1024 * 16  # 16KB chunks

    async def handle_stream_data(self, stream_id, data):
        if data.startswith(b'GET '):
            filename = data[4:].strip()
            print(f"Received request for: {filename.decode()}")
            
            if filename in self.video_files:
                print(f"Sending {filename.decode()} to client...")
                video_file = self.video_files[filename]
                
                try:
                    # Send video in chunks
                    video_file.seek(0)
                    chunk_count = 0
                    total_sent = 0
                    
                    while True:
                        chunk = video_file.read(self.chunk_size)
                        if not chunk:
                            break
                        
                        self._quic.send_stream_data(stream_id, chunk, end_stream=False)
                        chunk_count += 1
                        total_sent += len(chunk)
                        
                        # Control sending rate - small delay every 10 chunks
                        if chunk_count % 10 == 0:
                            await asyncio.sleep(0.001)
                    
                    # End stream
                    self._quic.send_stream_data(stream_id, b'', end_stream=True)
                    print(f"Completed sending {filename.decode()} - {total_sent} bytes in {chunk_count} chunks")
                    
                except Exception as e:
                    print(f"Error sending video: {e}")
                    self._quic.send_stream_data(stream_id, b'500 Server Error', end_stream=True)
            else:
                print(f"Video not found: {filename.decode()}")
                self._quic.send_stream_data(stream_id, b'404 Video Not Found', end_stream=True)

    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            asyncio.ensure_future(self.handle_stream_data(event.stream_id, event.data))

async def run_quic_server(host='10.0.0.1', port=4433, cc_algorithm='cubic'):
    # Generate certificates if they don't exist
    if not os.path.exists("cert.pem") or not os.path.exists("key.pem"):
        print("Generating SSL certificates...")
        result = os.system("openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj '/CN=localhost' >/dev/null 2>&1")
        if result == 0:
            print("✓ SSL certificates generated")
        else:
            print("✗ Failed to generate SSL certificates")
    
    configuration = QuicConfiguration(
        is_client=False,
        alpn_protocols=["video-stream"],
        max_datagram_frame_size=65536,
    )
    
    try:
        # Load certificates
        configuration.load_cert_chain("cert.pem", "key.pem")
    except Exception as e:
        print(f"Error loading certificates: {e}")
        return
    
    try:
        print(f"Starting QUIC Server on {host}:{port}...")
        server = await serve(
            host=host,
            port=port,
            configuration=configuration,
            create_protocol=VideoStreamHandler,
        )
        
        print(f"✓ QUIC Server running on {host}:{port}")
        print("Available videos: sample_240p.mp4, sample_480p.mp4, sample_720p.mp4, sample_1080p.mp4")
        print("Waiting for connections...")
        
        # Run forever
        await asyncio.Future()
        
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"✗ Port {port} is already in use")
            print("Try: sudo fuser -k {port}/tcp")
        else:
            print(f"✗ Failed to start QUIC server: {e}")
    except Exception as e:
        print(f"✗ Failed to start QUIC server: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='10.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=4433, help='Server port')
    
    args = parser.parse_args()
    
    print("Starting QUIC Video Streaming Server...")
    
    # Check if videos directory exists and has files
    if not os.path.exists('videos'):
        print("Creating videos directory...")
        os.makedirs('videos')
    
    video_files = os.listdir('videos') if os.path.exists('videos') else []
    if not video_files:
        print("Warning: No video files found in 'videos' directory")
        print("Please run: python3 setup.py to create sample videos")
    else:
        print(f"Found {len(video_files)} video files in videos directory")
    
    asyncio.run(run_quic_server(args.host, args.port))