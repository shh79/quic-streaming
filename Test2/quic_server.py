# quic_server.py
import os
import asyncio
from pathlib import Path
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, StreamReset, DatagramFrameReceived
from aioquic.asyncio.protocol import QuicConnectionProtocol


class VideoStreamHandler(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.video_dir = Path("../Video_Segments")
        self.active_streams = {}
        self.connection_active = True

    async def handle_stream_data(self, stream_id, data):
        print(f"Received request on stream {stream_id}: {data.decode()}")
        
        try:
            # Parse video request from client
            request_text = data.decode().strip()
            if request_text.startswith('GET '):
                filename = request_text[4:].strip()
                print(f"Client requested: {filename}")
                
                video_path = self.video_dir / filename
                
                # Check if file exists
                if not video_path.exists():
                    error_msg = f"ERROR: File not found: {filename}"
                    print(f"{error_msg}")
                    self._quic.send_stream_data(stream_id, error_msg.encode(), end_stream=True)
                    return
                
                print(f"Sending file: {video_path} (size: {video_path.stat().st_size} bytes)")
                await self.send_video_file(stream_id, video_path)
            else:
                print(f"Unknown request: {request_text}")
                
        except Exception as e:
            print(f"Error handling stream {stream_id}: {e}")
            import traceback
            traceback.print_exc()

    async def send_video_file(self, stream_id, video_path):
        """Send entire video file efficiently"""
        try:
            # Read the entire file first
            with open(video_path, 'rb') as f:
                file_data = f.read()
            
            print(f"Sending {len(file_data)} bytes on stream {stream_id}")
            
            # Send data in chunks
            chunk_size = 16 * 1024  # 16KB chunks (smaller for better flow control)
            total_chunks = (len(file_data) + chunk_size - 1) // chunk_size
            
            for i in range(0, len(file_data), chunk_size):
                chunk = file_data[i:i + chunk_size]
                is_final_chunk = (i + chunk_size >= len(file_data))
                
                # Send the chunk
                self._quic.send_stream_data(
                    stream_id, 
                    chunk, 
                    end_stream=is_final_chunk
                )
                
                # Force transmission
                self.transmit()
                
                # Small delay for flow control
                if i % (chunk_size * 5) == 0:  # Log every 5 chunks
                    progress = min(i + chunk_size, len(file_data))
                    print(f"Stream {stream_id}: Sent {progress}/{len(file_data)} bytes")
                
                await asyncio.sleep(0.001)  # Small delay
            
            print(f"Stream {stream_id}: File transfer complete - {len(file_data)} bytes sent")
            
        except Exception as e:
            print(f"Error sending file on stream {stream_id}: {e}")
            import traceback
            traceback.print_exc()

    def quic_event_received(self, event):
        print(f"Server received event: {type(event).__name__}")
        
        if isinstance(event, StreamDataReceived):
            print(f"Stream data received on stream {event.stream_id}, length: {len(event.data)}, end_stream: {event.end_stream}")
            # Process immediately
            asyncio.create_task(self.handle_stream_data(event.stream_id, event.data))
        elif isinstance(event, StreamReset):
            print(f"Stream {event.stream_id} was reset")
        elif isinstance(event, DatagramFrameReceived):
            pass  # Ignore datagram frames

    def connection_made(self, transport):
        print("New QUIC connection established")
        super().connection_made(transport)

    def connection_lost(self, exc):
        print(f"QUIC connection lost: {exc}")
        self.connection_active = False
        super().connection_lost(exc)


async def run_quic_server():
    configuration = QuicConfiguration(
        is_client=False,
        alpn_protocols=["video-stream"],
        max_datagram_frame_size=65536,
        idle_timeout=300,
        max_data=10485760,  # 10MB
        max_stream_data=1048576,  # 1MB per stream
    )
    
    # Load certificates
    cert_path = Path("../cert.pem")
    key_path = Path("../key.pem")
    
    try:
        configuration.load_cert_chain(cert_path, key_path)
        print("Certificates loaded successfully")
    except Exception as e:
        print(f"Error loading certificates: {e}")
        return

    try:
        print("Starting QUIC server on 10.0.0.1:4433...")
        server = await serve(
            host='10.0.0.1',
            port=4433,
            configuration=configuration,
            create_protocol=VideoStreamHandler,
        )
        
        print("QUIC Video Server is running!")
        print("Waiting for client connections...")
        
        # Run forever
        await asyncio.Future()
        
    except Exception as e:
        print(f"Server error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Starting QUIC Video Streaming Server...")
    try:
        asyncio.run(run_quic_server())
    except KeyboardInterrupt:
        print("\n Server stopped by user")