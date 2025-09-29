import asyncio
import time
import json
import argparse
from datetime import datetime
from pathlib import Path
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived

class QLogger:
    def __init__(self, log_dir="qlog"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.events = []
        self.start_time = time.time()
        
    def log_event(self, category, event_type, data=None, stream_id=None):
        timestamp = (time.time() - self.start_time) * 1000
        event = {
            "time": timestamp,
            "name": f"{category}:{event_type}",
            "data": data or {}
        }
        if stream_id is not None:
            event["data"]["stream_id"] = stream_id
        self.events.append(event)
        
    def log_connection_start(self, host, port):
        self.log_event("connection", "start", {
            "remote_address": f"{host}:{port}",
            "protocol": "QUIC"
        })
        
    def log_connection_established(self, connection_time):
        self.log_event("connection", "established", {
            "time_to_connect": connection_time * 1000
        })
        
    def log_stream_request(self, stream_id, video_name):
        self.log_event("stream", "request", {
            "video_name": video_name.decode(),
            "method": "GET"
        }, stream_id)
        
    def log_data_received(self, stream_id, data_length, is_first=False, is_last=False):
        self.log_event("stream", "data_received", {
            "bytes_received": data_length,
            "is_first_chunk": is_first,
            "is_last_chunk": is_last
        }, stream_id)
        
    def log_transfer_complete(self, stream_id, total_bytes, total_time, transfer_rate):
        self.log_event("stream", "transfer_complete", {
            "total_bytes": total_bytes,
            "total_time_ms": total_time * 1000,
            "transfer_rate_kbps": transfer_rate
        }, stream_id)
        
    def save_qlog(self, filename_prefix="quic_client"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.log_dir / f"{filename_prefix}_{timestamp}.qlog"
        
        qlog_data = {
            "qlog_version": "draft-01",
            "title": "QUIC Client QLog",
            "trace": {
                "events": self.events
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(qlog_data, f, indent=2)
        return filename

class VideoStreamProtocol:
    def __init__(self, quic, qlogger):
        self._quic = quic
        self.qlogger = qlogger
        self.video_data = b''
        self.start_time = time.time()
        self.first_chunk_time = 0
        self.connection_time = 0
        self.current_stream_id = None
        self.video_name = None
        self.transfer_complete = asyncio.Event()
        self.chunk_count = 0
        self.connection_established = False

    async def request_video(self, video_name: bytes):
        self.video_name = video_name
        self.current_stream_id = self._quic.get_next_available_stream_id()
        
        self.qlogger.log_stream_request(self.current_stream_id, video_name)
        
        # Send request
        request_data = f"GET {video_name.decode()}".encode()
        self._quic.send_stream_data(
            stream_id=self.current_stream_id,
            data=request_data,
            end_stream=False
        )
        
        print(f"Requested video: {video_name.decode()}")
        await self.transfer_complete.wait()

    def quic_event_received(self, event):
        if not self.connection_established:
            self.connection_established = True
            self.connection_time = time.time() - self.start_time
            self.qlogger.log_connection_established(self.connection_time)
            print(f"✓ Connection established in {self.connection_time:.3f}s")
        
        if isinstance(event, StreamDataReceived) and event.stream_id == self.current_stream_id:
            self.chunk_count += 1
            is_first_chunk = not self.video_data
            is_last_chunk = event.end_stream
            
            if is_first_chunk:
                self.first_chunk_time = time.time() - self.start_time
                print(f"✓ First data received at {self.first_chunk_time:.3f}s")
            
            # Log data reception
            self.qlogger.log_data_received(
                event.stream_id, 
                len(event.data),
                is_first=is_first_chunk,
                is_last=is_last_chunk
            )
            
            self.video_data += event.data
            
            if self.chunk_count % 10 == 0:
                print(f"  Received {len(self.video_data)/1024:.1f} KB...")
            
            if event.end_stream:
                self._handle_transfer_complete()

    def _handle_transfer_complete(self):
        total_time = time.time() - self.start_time
        transfer_time = total_time - self.first_chunk_time
        transfer_rate = (len(self.video_data) / 1024) / transfer_time if transfer_time > 0 else 0
        
        print(f"\n=== TRANSFER COMPLETE ===")
        print(f"Video: {self.video_name.decode()}")
        print(f"Total time: {total_time:.3f} seconds")
        print(f"Startup delay: {self.first_chunk_time:.3f} seconds")
        print(f"Video size: {len(self.video_data)/1024/1024:.2f} MB")
        print(f"Transfer rate: {transfer_rate:.2f} KB/s")
        print(f"Chunks received: {self.chunk_count}")
        
        # Log transfer completion
        self.qlogger.log_transfer_complete(
            self.current_stream_id,
            len(self.video_data),
            total_time,
            transfer_rate
        )
        
        # Save qlog file
        qlog_file = self.qlogger.save_qlog(f"quic_{self.video_name.decode().replace('.', '_')}")
        print(f"QLog saved: {qlog_file}")
        
        self._save_video()
        self.transfer_complete.set()

    def _save_video(self):
        filename = f"received_{self.video_name.decode()}"
        with open(filename, 'wb') as f:
            f.write(self.video_data)
        print(f"Video saved: {filename}")

class VideoStreamClient:
    def __init__(self):
        self.configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=["video-stream"],
            max_datagram_frame_size=65536,
            verify_mode=False
        )

    async def run(self, host: str, port: int, video_name: bytes):
        print(f"Connecting to {host}:{port}...")
        
        qlogger = QLogger()
        qlogger.log_connection_start(host, port)
        
        try:
            async with connect(
                host=host,
                port=port,
                configuration=self.configuration,
                create_protocol=lambda quic: VideoStreamProtocol(quic, qlogger)
            ) as protocol:
                print("✓ Connected to server")
                await protocol.request_video(video_name)
                
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            print("Make sure the QUIC server is running and accessible")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='10.0.0.1', help='QUIC server host')
    parser.add_argument('--port', type=int, default=4433, help='QUIC server port')
    parser.add_argument('--video', default='sample_240p.mp4', help='Video file to request')
    
    args = parser.parse_args()
    
    client = VideoStreamClient()
    await client.run(args.host, args.port, args.video.encode())

if __name__ == "__main__":
    asyncio.run(main())