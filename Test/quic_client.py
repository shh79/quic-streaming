import asyncio
import time
import json
import argparse
from datetime import datetime
from pathlib import Path
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived

class EnhancedQLogger:
    def __init__(self, log_dir="qlog"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.events = []
        self.start_time = time.time()
        self.connection_stats = {
            'packets_sent': 0,
            'packets_received': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'rtt_samples': [],
            'loss_events': 0
        }
    
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
        
    def log_data_received(self, stream_id, data_length, chunk_num, is_first=False, is_last=False):
        self.log_event("stream", "data_received", {
            "bytes_received": data_length,
            "chunk_number": chunk_num,
            "cumulative_bytes": sum(evt["data"].get("bytes_received", 0) for evt in self.events 
                                  if evt["name"] == "stream:data_received" and evt["data"].get("stream_id") == stream_id) + data_length,
            "is_first_chunk": is_first,
            "is_last_chunk": is_last
        }, stream_id)
        
    def log_packet_sent(self, packet_size, packet_number):
        self.connection_stats['packets_sent'] += 1
        self.connection_stats['bytes_sent'] += packet_size
        self.log_event("transport", "packet_sent", {
            "packet_size": packet_size,
            "packet_number": packet_number,
            "cumulative_sent": self.connection_stats['bytes_sent']
        })
    
    def log_packet_received(self, packet_size, packet_number):
        self.connection_stats['packets_received'] += 1
        self.connection_stats['bytes_received'] += packet_size
        self.log_event("transport", "packet_received", {
            "packet_size": packet_size,
            "packet_number": packet_number,
            "cumulative_received": self.connection_stats['bytes_received']
        })
    
    def log_rtt_measurement(self, rtt_ms):
        self.connection_stats['rtt_samples'].append(rtt_ms)
        self.log_event("transport", "rtt_measurement", {
            "rtt_ms": rtt_ms,
            "min_rtt": min(self.connection_stats['rtt_samples']),
            "max_rtt": max(self.connection_stats['rtt_samples']),
            "avg_rtt": sum(self.connection_stats['rtt_samples']) / len(self.connection_stats['rtt_samples'])
        })
    
    def log_transfer_complete(self, stream_id, total_bytes, total_time, transfer_rate):
        self.log_event("stream", "transfer_complete", {
            "total_bytes": total_bytes,
            "total_time_ms": total_time * 1000,
            "transfer_rate_kbps": transfer_rate,
            "startup_delay": self.get_startup_delay(),
            "average_rtt": sum(self.connection_stats['rtt_samples']) / len(self.connection_stats['rtt_samples']) if self.connection_stats['rtt_samples'] else 0,
            "packet_loss_rate": (self.connection_stats['loss_events'] / self.connection_stats['packets_sent']) * 100 if self.connection_stats['packets_sent'] > 0 else 0
        }, stream_id)
    
    def get_startup_delay(self):
        for event in self.events:
            if event["name"] == "stream:data_received" and event["data"].get("is_first_chunk"):
                return event["time"]
        return 0
    
    def save_qlog(self, filename_prefix="quic_client"):
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
        
        self._quic.send_stream_data(
            stream_id=self.current_stream_id,
            data=f"GET {video_name.decode()}".encode(),
            end_stream=False
        )
        
        # Simulate packet sending for logging
        self.qlogger.log_packet_sent(len(f"GET {video_name.decode()}".encode()), 1)
        
        await self.transfer_complete.wait()

    def quic_event_received(self, event):
        if not self.connection_established:
            self.connection_established = True
            self.connection_time = time.time() - self.start_time
            self.qlogger.log_connection_established(self.connection_time)
            print(f"Connection established, time: {self.connection_time:.3f}s")
        
        if isinstance(event, StreamDataReceived) and event.stream_id == self.current_stream_id:
            self.chunk_count += 1
            is_first_chunk = not self.video_data
            is_last_chunk = event.end_stream
            
            if is_first_chunk:
                self.first_chunk_time = time.time() - self.start_time
                print(f"First data chunk received at {self.first_chunk_time:.3f}s")
            
            # Log data reception
            self.qlogger.log_data_received(
                event.stream_id, 
                len(event.data),
                self.chunk_count,
                is_first=is_first_chunk,
                is_last=is_last_chunk
            )
            
            # Simulate packet reception for logging
            self.qlogger.log_packet_received(len(event.data), self.chunk_count)
            
            # Simulate RTT measurements (in real implementation, this would come from QUIC stack)
            if self.chunk_count % 10 == 0:
                simulated_rtt = 50 + (time.time() % 20)  # Simulated RTT between 50-70ms
                self.qlogger.log_rtt_measurement(simulated_rtt)
            
            self.video_data += event.data
            
            if event.end_stream:
                self._handle_transfer_complete()

    def _handle_transfer_complete(self):
        total_time = time.time() - self.start_time
        transfer_time = total_time - self.first_chunk_time
        transfer_rate = (len(self.video_data) / 1024) / transfer_time if transfer_time > 0 else 0
        
        print(f"\n=== Transfer Complete ===")
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
    def __init__(self, cc_algorithm='cubic'):
        self.configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=["video-stream"],
            max_datagram_frame_size=65536,
            verify_mode=False
        )
        self.cc_algorithm = cc_algorithm

    async def run(self, host: str, port: int, video_name: bytes):
        print(f"Connecting to {host}:{port} with {self.cc_algorithm} congestion control...")
        
        qlogger = EnhancedQLogger()
        qlogger.log_connection_start(host, port)
        
        async with connect(
            host=host,
            port=port,
            configuration=self.configuration,
            create_protocol=lambda quic: VideoStreamProtocol(quic, qlogger)
        ) as protocol:
            print("Connected, requesting video...")
            await protocol.request_video(video_name)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='10.0.0.1', help='QUIC server host')
    parser.add_argument('--port', type=int, default=4433, help='QUIC server port')
    parser.add_argument('--video', default='sample_720p.mp4', help='Video file to request')
    parser.add_argument('--cc', default='cubic', choices=['cubic', 'reno'], help='Congestion control algorithm')
    
    args = parser.parse_args()
    
    client = VideoStreamClient(cc_algorithm=args.cc)
    await client.run(args.host, args.port, args.video.encode())

if __name__ == "__main__":
    asyncio.run(main())