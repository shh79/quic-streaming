# quic_client.py
import asyncio
import time
import json
from datetime import datetime
from pathlib import Path
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, DatagramFrameReceived
from aioquic.quic.logger import QuicLogger
from aioquic.asyncio.protocol import QuicConnectionProtocol


class StreamQLogger:
    """Stream-level logging"""
    
    def __init__(self, log_dir="qlog"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.events = []
        self.start_time = time.time()

    def log_event(self, category, event_type, data=None, stream_id=None):
        timestamp = (time.time() - self.start_time) * 1000  # ms
        event = {"time": timestamp, "name": f"{category}:{event_type}", "data": data or {}}
        if stream_id is not None:
            event["data"]["stream_id"] = stream_id
        self.events.append(event)

    def log_connection_start(self, host, port):
        self.log_event("connection", "start", {"remote_address": f"{host}:{port}", "protocol": "QUIC"})

    def log_connection_established(self):
        self.log_event("connection", "established", {"time_to_connect": (time.time() - self.start_time) * 1000})

    def log_stream_request(self, stream_id, video_name):
        self.log_event("stream", "request", {"video_name": video_name.decode(), "method": "GET"}, stream_id)

    def log_data_received(self, stream_id, data_length, is_first_chunk=False, is_last_chunk=False):
        cumulative = sum(evt["data"].get("bytes_received", 0)
                        for evt in self.events
                        if evt["name"] == "stream:data_received" and evt["data"].get("stream_id") == stream_id)
        cumulative += data_length
        self.log_event("stream", "data_received", {
            "bytes_received": data_length,
            "cumulative_bytes": cumulative,
            "is_first_chunk": is_first_chunk,
            "is_last_chunk": is_last_chunk
        }, stream_id)

    def log_transfer_complete(self, stream_id, total_bytes, total_time, transfer_rate):
        self.log_event("stream", "transfer_complete", {
            "total_bytes": total_bytes,
            "total_time_ms": total_time * 1000,
            "transfer_rate_kbps": transfer_rate * 8 / 1024
        }, stream_id)

    def save_qlog(self, filename_prefix="stream"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.log_dir / f"{filename_prefix}_{timestamp}.qlog"
        qlog_data = {
            "qlog_version": "draft-01",
            "title": "QUIC Client Stream QLog",
            "description": "Stream-level events",
            "trace": {
                "vantage_point": {"name": "quic-video-client", "type": "client"},
                "common_fields": {"reference_time": self.start_time * 1000, "time_units": "ms"},
                "events": self.events
            }
        }
        with open(filename, "w") as f:
            json.dump(qlog_data, f, indent=2)
        print(f"💾 Stream QLog saved to: {filename}")


class VideoStreamProtocol(QuicConnectionProtocol):
    """QUIC Protocol with adaptive bitrate streaming"""
    
    def __init__(self, *args, stream_qlogger=None, bitrates=None, segments_per_bitrate=5, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream_qlogger = stream_qlogger
        self.packet_logger = self._quic._quic_logger
        self.bitrates = bitrates or [360, 720, 1080]
        self.current_bitrate = min(self.bitrates)
        self.segment_index = 0
        self.segments_per_bitrate = segments_per_bitrate
        self.video_data = b""
        self.start_time = time.time()
        self.first_chunk_time = 0
        self.current_stream_id = None
        self.video_name = None
        self.transfer_complete = asyncio.Event()
        self.connection_established = False
        self.last_chunk_time = 0
        self.received_bytes = 0

    def get_next_stream_id(self) -> int:
        stream_id = self._quic.get_next_available_stream_id()
        print(f"🆔 Using stream ID: {stream_id}")
        return stream_id

    async def request_next_segment(self):
        if self.segment_index >= self.segments_per_bitrate:
            print("🎉 All segments completed!")
            return False

        # Determine video filename based on current bitrate
        if self.current_bitrate == 360:
            video_name = f"sample_low_seg{self.segment_index}.mp4"
        elif self.current_bitrate == 720:
            video_name = f"sample_medium_seg{self.segment_index}.mp4"
        else:  # 1080
            video_name = f"sample_high_seg{self.segment_index}.mp4"
        
        print(f"📨 Requesting segment {self.segment_index} at {self.current_bitrate}p: {video_name}")
        
        self.current_stream_id = self.get_next_stream_id()
        self.video_data = b""
        self.received_bytes = 0
        self.transfer_complete.clear()

        # Log stream request
        if self.stream_qlogger:
            self.stream_qlogger.log_stream_request(self.current_stream_id, video_name.encode())

        # Send GET request for segment
        request_data = f"GET {video_name}".encode()
        print(f"📤 Sending request: {request_data} on stream {self.current_stream_id}")
        
        # Send request and immediately end the stream for request
        self._quic.send_stream_data(
            stream_id=self.current_stream_id,
            data=request_data,
            end_stream=True  # End stream after request
        )
        
        # Force transmission
        self.transmit()

        print(f"⏳ Waiting for video data on stream {self.current_stream_id}...")
        start_chunk_time = time.time()
        
        # Wait for transfer to complete with timeout
        try:
            await asyncio.wait_for(self.transfer_complete.wait(), timeout=30.0)
            self.last_chunk_time = time.time() - start_chunk_time
        except asyncio.TimeoutError:
            print(f"⏰ Timeout waiting for segment {self.segment_index}")
            return False

        # Calculate throughput
        if self.last_chunk_time > 0:
            throughput_kbps = (self.received_bytes * 8) / self.last_chunk_time / 1000
        else:
            throughput_kbps = 0
            
        print(f"✅ Segment {self.segment_index} finished: {self.received_bytes} bytes, {throughput_kbps:.2f} kbps, time: {self.last_chunk_time:.2f}s")

        # ABR decision
        idx = self.bitrates.index(self.current_bitrate)
        if throughput_kbps > self.current_bitrate * 1.5 and idx < len(self.bitrates) - 1:
            self.current_bitrate = self.bitrates[idx + 1]
            print(f"⬆️ Switching UP to {self.current_bitrate}p")
        elif throughput_kbps < self.current_bitrate * 0.8 and idx > 0:
            self.current_bitrate = self.bitrates[idx - 1]
            print(f"⬇️ Switching DOWN to {self.current_bitrate}p")
        else:
            print(f"🔄 Keeping bitrate {self.current_bitrate}p")

        self.segment_index += 1
        return True

    def quic_event_received(self, event):
        if not self.connection_established:
            self.connection_established = True
            if self.stream_qlogger:
                self.stream_qlogger.log_connection_established()
            print(f"🔗 Connection established after {(time.time() - self.start_time):.3f}s")

        if isinstance(event, StreamDataReceived):
            print(f"📥 Client received data on stream {event.stream_id}, length: {len(event.data)}, end_stream: {event.end_stream}")
            
            if event.stream_id == self.current_stream_id:
                is_first_chunk = not self.video_data
                is_last_chunk = event.end_stream

                if is_first_chunk:
                    self.first_chunk_time = time.time() - self.start_time
                    print(f"🎬 First chunk received for stream {event.stream_id}")

                if self.stream_qlogger:
                    self.stream_qlogger.log_data_received(
                        event.stream_id, len(event.data),
                        is_first_chunk=is_first_chunk,
                        is_last_chunk=is_last_chunk
                    )

                self.video_data += event.data
                self.received_bytes += len(event.data)

                if event.end_stream:
                    total_time = time.time() - self.start_time
                    transfer_time = total_time - self.first_chunk_time
                    
                    if transfer_time > 0:
                        transfer_rate = (self.received_bytes / 1024) / transfer_time  # KB/s
                    else:
                        transfer_rate = 0

                    if self.stream_qlogger:
                        self.stream_qlogger.log_transfer_complete(
                            self.current_stream_id, self.received_bytes, total_time, transfer_rate
                        )

                    # Save chunk
                    Path('results').mkdir(exist_ok=True)
                    chunk_filename = Path('results') / f"quic_received_{self.current_bitrate}p_seg{self.segment_index}.mp4"
                    with open(chunk_filename, "wb") as f:
                        f.write(self.video_data)
                    print(f"💾 Segment saved: {chunk_filename} ({self.received_bytes} bytes)")

                    self.transfer_complete.set()
                    print(f"✅ Transfer complete for stream {event.stream_id}")

        elif isinstance(event, DatagramFrameReceived):
            pass  # Ignore datagram frames


class VideoStreamClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=["video-stream"],
            max_datagram_frame_size=65536,
            verify_mode=False,
            max_data=10485760,  # 10MB
            max_stream_data=1048576,  # 1MB per stream
        )

        self.packet_logger = QuicLogger()
        self.configuration.quic_logger = self.packet_logger
        self.stream_logger = StreamQLogger()

    async def run(self):
        print(f"🔗 Connecting to {self.host}:{self.port}...")
        
        # Create qlogger instance for connection logging
        self.stream_logger.log_connection_start(self.host, self.port)
        
        try:
            async with connect(
                host=self.host,
                port=self.port,
                configuration=self.configuration,
                create_protocol=lambda *args, **kwargs: VideoStreamProtocol(*args, stream_qlogger=self.stream_logger, **kwargs)
            ) as protocol:
                print("✅ Connected, starting ABR streaming...")
                
                segment_count = 0
                while await protocol.request_next_segment():
                    segment_count += 1
                    print(f"🎉 Successfully completed segment {segment_count}")
                    # Small delay between segments
                    await asyncio.sleep(0.5)
                
                print(f"🎊 Streaming completed! Total segments: {segment_count}")
        
        except Exception as e:
            print(f"💥 Connection error: {e}")
            import traceback
            traceback.print_exc()
        
        self.stream_logger.save_qlog('abr_video')

        Path("qlog").mkdir(exist_ok=True)
        packet_log_file = Path("qlog") / f"packet_trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.qlog"
        
        with open(packet_log_file, "w") as f:
            json.dump(self.packet_logger.to_dict(), f, indent=2)

        print(f"💾 Packet-Level Qlog saved to: {packet_log_file}")


async def main():
    client = VideoStreamClient("10.0.0.1", 4433)
    await client.run()


if __name__ == "__main__":
    print("🎬 Starting QUIC Video Streaming Client...")
    asyncio.run(main())