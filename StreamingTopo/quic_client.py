import asyncio
import time
import json
from datetime import datetime
from pathlib import Path
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
from aioquic.asyncio.protocol import QuicConnectionProtocol

class QLogger:
    def __init__(self, log_dir="qlog"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.events = []
        self.start_time = time.time()
        
    def log_event(self, category, event_type, data=None, stream_id=None):
        """Log a QUIC event with timestamp"""
        timestamp = (time.time() - self.start_time) * 1000  # Convert to milliseconds
        
        event = {
            "time": timestamp,
            "name": f"{category}:{event_type}",
            "data": data or {}
        }
        
        if stream_id is not None:
            event["data"]["stream_id"] = stream_id
            
        self.events.append(event)
        
    def log_connection_start(self, host, port):
        """Log connection initiation"""
        self.log_event("connection", "start", {
            "remote_address": f"{host}:{port}",
            "protocol": "QUIC"
        })
        
    def log_connection_established(self):
        """Log successful connection"""
        self.log_event("connection", "established", {
            "time_to_connect": (time.time() - self.start_time) * 1000
        })
        
    def log_stream_request(self, stream_id, video_name):
        """Log stream request"""
        self.log_event("stream", "request", {
            "video_name": video_name.decode(),
            "method": "GET"
        }, stream_id)
        
    def log_data_received(self, stream_id, data_length, is_first_chunk=False, is_last_chunk=False):
        """Log data reception"""
        self.log_event("stream", "data_received", {
            "bytes_received": data_length,
            "cumulative_bytes": sum(evt["data"].get("bytes_received", 0) for evt in self.events 
                                  if evt["name"] == "stream:data_received" and evt["data"].get("stream_id") == stream_id) + data_length,
            "is_first_chunk": is_first_chunk,
            "is_last_chunk": is_last_chunk
        }, stream_id)
        
    def log_transfer_complete(self, stream_id, total_bytes, total_time, transfer_rate):
        """Log transfer completion"""
        self.log_event("stream", "transfer_complete", {
            "total_bytes": total_bytes,
            "total_time_ms": total_time * 1000,
            "transfer_rate_kbps": transfer_rate * 8 / 1024  # Convert to kbps
        }, stream_id)
        
    def save_qlog(self, filename_prefix="quic_client"):
        """Save qlog events to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.log_dir / f"{filename_prefix}_{timestamp}.qlog"
        
        qlog_data = {
            "qlog_version": "draft-01",
            "title": "QUIC Client QLog",
            "description": "QUIC video streaming client events",
            "trace": {
                "vantage_point": {
                    "name": "quic-video-client",
                    "type": "client"
                },
                "common_fields": {
                    "reference_time": self.start_time * 1000,
                    "time_units": "ms"
                },
                "events": self.events
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(qlog_data, f, indent=2)
            
        print(f"QLog saved to: {filename}")
        return filename

class VideoStreamProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.video_data = b''
        self.start_time = time.time()
        self.first_chunk_time = 0
        self.connection_time = 0
        self.current_stream_id = None
        self.video_name = None
        self.transfer_complete = asyncio.Event()
        self.qlogger = QLogger()
        self.connection_established = False

    def get_next_stream_id(self) -> int:
        """Get the next available client-initiated stream ID"""
        return self._quic.get_next_available_stream_id()

    async def request_video(self, video_name: bytes) -> None:
        """Initiate video request on a new stream"""
        self.video_name = video_name
        self.current_stream_id = self.get_next_stream_id()
        
        # Log the stream request
        self.qlogger.log_stream_request(self.current_stream_id, video_name)
        
        self._quic.send_stream_data(
            stream_id=self.current_stream_id,
            data=f"GET {video_name.decode()}".encode(),
            end_stream=False
        )
        
        await self.transfer_complete.wait()

    def quic_event_received(self, event):
        """Handle incoming QUIC events"""
        # Log connection establishment
        if not self.connection_established:
            self.connection_established = True
            self.connection_time = time.time() - self.start_time
            self.qlogger.log_connection_established()
            print(f"Connection established, time: {self.connection_time:.3f}s")
        
        if isinstance(event, StreamDataReceived) and event.stream_id == self.current_stream_id:
            is_first_chunk = not self.video_data
            is_last_chunk = event.end_stream
            
            if is_first_chunk:
                self.first_chunk_time = time.time() - self.start_time
                print(f"First packet received on stream {self.current_stream_id}")
            
            # Log data reception
            self.qlogger.log_data_received(
                event.stream_id, 
                len(event.data),
                is_first_chunk=is_first_chunk,
                is_last_chunk=is_last_chunk
            )
            
            self.video_data += event.data
            
            if event.end_stream:
                self._handle_transfer_complete()

    def _handle_transfer_complete(self):
        """Finalize transfer and print statistics"""
        total_time = time.time() - self.start_time
        transfer_time = total_time - self.first_chunk_time
        transfer_rate = (len(self.video_data) / 1024) / transfer_time
        
        print(f"\nTransfer complete for {self.video_name.decode()}")
        print(f"Total time: {total_time:.3f} seconds")
        print(f"Video size: {len(self.video_data)/1024:.2f} KB")
        print(f"Transfer rate: {transfer_rate:.2f} KB/s")
        
        # Log transfer completion
        self.qlogger.log_transfer_complete(
            self.current_stream_id,
            len(self.video_data),
            total_time,
            transfer_rate
        )
        
        # Save qlog file
        qlog_file = self.qlogger.save_qlog(f"video_{self.video_name.decode().replace('.', '_')}")
        print(f"QLog file: {qlog_file}")
        
        self._save_video()
        self.transfer_complete.set()

    def _save_video(self):
        """Save video data to file"""
        filename = f"received_{self.video_name.decode()}"
        with open(filename, 'wb') as f:
            f.write(self.video_data)
        print(f"Video saved as {filename}")

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
        
        # Create qlogger instance for connection logging
        qlogger = QLogger()
        qlogger.log_connection_start(host, port)
        
        async with connect(
            host=host,
            port=port,
            configuration=self.configuration,
            create_protocol=VideoStreamProtocol
        ) as protocol:
            # Pass the qlogger to the protocol instance
            protocol.qlogger = qlogger
            print("Connected, requesting video...")
            await protocol.request_video(video_name)

async def main():
    client = VideoStreamClient()
    await client.run("10.0.0.1", 4433, b"sample.mp4")

if __name__ == "__main__":
    asyncio.run(main())