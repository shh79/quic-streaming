# quic_client.py
import asyncio
import time
import json
import csv
import os
from datetime import datetime
from pathlib import Path
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, DatagramFrameReceived
from aioquic.quic.logger import QuicLogger
from aioquic.asyncio.protocol import QuicConnectionProtocol
from collections import deque


class MetricsCalculator:
    """Comprehensive metrics calculation for QUIC streaming"""
    
    def __init__(self, segment_duration=2.0):
        self.segment_duration = segment_duration
        
        # Metrics storage
        self.segment_metrics = []
        self.throughput_history = deque(maxlen=5)
        self.rtt_history = deque(maxlen=10)
        
        # Real-time state
        self.buffer_level = 0.0
        self.rebuffering_count = 0
        self.total_rebuffering_duration = 0.0
        self.rebuffering_start_time = None
        self.playback_position = 0.0
        self.current_bitrate = 0
        self.bitrate_switches = 0
        self.previous_bitrate = 0
        
        # Create results directory
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        
        # Initialize metrics CSV
        self.metrics_file = self.results_dir / f"quic_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._initialize_metrics_file()

    def _initialize_metrics_file(self):
        """Initialize CSV file with headers"""
        with open(self.metrics_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'segment_index', 'bitrate', 'segment_size_bytes',
                'download_time_sec', 'throughput_bps', 'smoothed_throughput_bps',
                'rtt_estimate_sec', 'buffer_level_sec', 'rebuffering_count',
                'total_rebuffering_duration_sec', 'playback_position_sec',
                'is_rebuffering', 'bitrate_switch', 'goodput_bps', 'packet_loss_estimate'
            ])

    def calculate_throughput(self, data_size, download_time):
        """Calculate throughput in bits per second"""
        if download_time <= 0:
            return 0
        throughput = (data_size * 8) / download_time
        self.throughput_history.append(throughput)
        return throughput

    def get_smoothed_throughput(self):
        """Get moving average throughput"""
        if not self.throughput_history:
            return 0
        return sum(self.throughput_history) / len(self.throughput_history)

    def estimate_rtt(self, download_time, segment_size):
        """Estimate RTT based on download characteristics"""
        # Simple RTT estimation: download time for small segments approximates RTT
        if segment_size < 10000:  # Small segments likely control/data mix
            rtt = download_time
        else:
            # For larger segments, RTT is a fraction of download time
            rtt = download_time * 0.1  # Approximation
        self.rtt_history.append(rtt)
        return rtt

    def get_smoothed_rtt(self):
        """Get smoothed RTT estimate"""
        if not self.rtt_history:
            return 0
        return sum(self.rtt_history) / len(self.rtt_history)

    def update_buffer(self, download_time, is_segment_complete=False):
        """Update buffer level and track rebuffering"""
        was_rebuffering = False
        
        # Simulate playback consuming buffer
        if self.buffer_level > 0:
            self.buffer_level = max(0, self.buffer_level - download_time)
        
        # Check for rebuffering start
        if self.buffer_level <= 0 and self.rebuffering_start_time is None:
            self.rebuffering_start_time = time.time()
            self.rebuffering_count += 1
            was_rebuffering = True
        
        # Add segment to buffer when complete
        if is_segment_complete:
            self.buffer_level += self.segment_duration
        
        # Check for rebuffering end
        if self.rebuffering_start_time is not None and self.buffer_level > 0:
            rebuffering_duration = time.time() - self.rebuffering_start_time
            self.total_rebuffering_duration += rebuffering_duration
            self.rebuffering_start_time = None
        
        return was_rebuffering

    def record_segment_metrics(self, segment_index, bitrate, segment_size, 
                             download_time, timestamp, is_complete=False):
        """Record all metrics for current segment"""
        
        # Calculate metrics
        throughput = self.calculate_throughput(segment_size, download_time)
        smoothed_throughput = self.get_smoothed_throughput()
        rtt_estimate = self.estimate_rtt(download_time, segment_size)
        smoothed_rtt = self.get_smoothed_rtt()
        
        # Update buffer
        is_rebuffering = self.update_buffer(download_time, is_complete)
        
        # Update playback position
        if is_complete:
            self.playback_position = segment_index * self.segment_duration
        
        # Track bitrate switches
        bitrate_switch = 0
        if self.previous_bitrate != 0 and bitrate != self.previous_bitrate:
            bitrate_switch = 1
            self.bitrate_switches += 1
        self.previous_bitrate = bitrate
        
        # Calculate goodput (effective throughput)
        goodput = min(throughput, bitrate) if bitrate > 0 else throughput
        
        # Simple packet loss estimation (based on throughput variance)
        packet_loss_estimate = 0
        if len(self.throughput_history) > 1:
            avg_throughput = sum(self.throughput_history) / len(self.throughput_history)
            if avg_throughput > 0:
                throughput_variance = abs(throughput - avg_throughput) / avg_throughput
                packet_loss_estimate = min(throughput_variance, 1.0)
        
        metrics = {
            'timestamp': timestamp,
            'segment_index': segment_index,
            'bitrate': bitrate,
            'segment_size_bytes': segment_size,
            'download_time_sec': download_time,
            'throughput_bps': throughput,
            'smoothed_throughput_bps': smoothed_throughput,
            'rtt_estimate_sec': smoothed_rtt,
            'buffer_level_sec': self.buffer_level,
            'rebuffering_count': self.rebuffering_count,
            'total_rebuffering_duration_sec': self.total_rebuffering_duration,
            'playback_position_sec': self.playback_position,
            'is_rebuffering': is_rebuffering,
            'bitrate_switch': bitrate_switch,
            'goodput_bps': goodput,
            'packet_loss_estimate': packet_loss_estimate
        }
        
        self.segment_metrics.append(metrics)
        self._save_metrics_to_csv(metrics)
        
        return metrics

    def _save_metrics_to_csv(self, metrics):
        """Save metrics to CSV file"""
        with open(self.metrics_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                metrics['timestamp'],
                metrics['segment_index'],
                metrics['bitrate'],
                metrics['segment_size_bytes'],
                metrics['download_time_sec'],
                metrics['throughput_bps'],
                metrics['smoothed_throughput_bps'],
                metrics['rtt_estimate_sec'],
                metrics['buffer_level_sec'],
                metrics['rebuffering_count'],
                metrics['total_rebuffering_duration_sec'],
                metrics['playback_position_sec'],
                metrics['is_rebuffering'],
                metrics['bitrate_switch'],
                metrics['goodput_bps'],
                metrics['packet_loss_estimate']
            ])

    def generate_summary_report(self):
        """Generate a summary report of all metrics"""
        if not self.segment_metrics:
            return
            
        summary_file = self.results_dir / f"quic_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(summary_file, 'w') as f:
            f.write("=== QUIC Streaming Metrics Summary ===\n")
            f.write(f"Total segments downloaded: {len([m for m in self.segment_metrics if m['segment_index'] > 0])}\n")
            f.write(f"Total rebuffering events: {self.rebuffering_count}\n")
            f.write(f"Total rebuffering duration: {self.total_rebuffering_duration:.2f} seconds\n")
            
            # Throughput statistics
            throughputs = [m['throughput_bps'] for m in self.segment_metrics if m['throughput_bps'] > 0]
            if throughputs:
                f.write(f"Average throughput: {sum(throughputs) / len(throughputs) / 1e6:.2f} Mbps\n")
                f.write(f"Max throughput: {max(throughputs) / 1e6:.2f} Mbps\n")
                f.write(f"Min throughput: {min(throughputs) / 1e6:.2f} Mbps\n")
            
            # RTT statistics
            rtts = [m['rtt_estimate_sec'] for m in self.segment_metrics if m['rtt_estimate_sec'] > 0]
            if rtts:
                f.write(f"Average RTT: {sum(rtts) / len(rtts) * 1000:.1f} ms\n")
                f.write(f"Max RTT: {max(rtts) * 1000:.1f} ms\n")
            
            # Buffer statistics
            buffers = [m['buffer_level_sec'] for m in self.segment_metrics]
            f.write(f"Maximum buffer level: {max(buffers):.2f} seconds\n")
            f.write(f"Average buffer level: {sum(buffers) / len(buffers):.2f} seconds\n")
            
            # Bitrate statistics
            f.write(f"Bitrate switches: {self.bitrate_switches}\n")
            
            # Goodput efficiency
            goodputs = [m['goodput_bps'] for m in self.segment_metrics if m['goodput_bps'] > 0]
            throughputs = [m['throughput_bps'] for m in self.segment_metrics if m['throughput_bps'] > 0]
            if goodputs and throughputs:
                efficiency = sum(goodputs) / sum(throughputs) * 100
                f.write(f"Goodput efficiency: {efficiency:.1f}%\n")
        
        print(f"📊 QUIC summary report saved: {summary_file}")


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

    def log_metrics(self, metrics):
        """Log comprehensive metrics"""
        self.log_event("metrics", "segment_complete", {
            "segment_index": metrics['segment_index'],
            "bitrate": metrics['bitrate'],
            "throughput_bps": metrics['throughput_bps'],
            "smoothed_throughput_bps": metrics['smoothed_throughput_bps'],
            "rtt_estimate_ms": metrics['rtt_estimate_sec'] * 1000,
            "buffer_level_sec": metrics['buffer_level_sec'],
            "rebuffering_count": metrics['rebuffering_count'],
            "is_rebuffering": metrics['is_rebuffering']
        })

    def save_qlog(self, filename_prefix="stream"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.log_dir / f"{filename_prefix}_{timestamp}.qlog"
        qlog_data = {
            "qlog_version": "draft-01",
            "title": "QUIC Client Stream QLog",
            "description": "Stream-level events with metrics",
            "trace": {
                "vantage_point": {"name": "quic-video-client", "type": "client"},
                "common_fields": {"reference_time": self.start_time * 1000, "time_units": "ms"},
                "events": self.events
            }
        }
        with open(filename, "w") as f:
            json.dump(qlog_data, f, indent=2)
        print(f"Stream QLog saved to: {filename}")

class DetailedQuicLogger(QuicLogger):
    """Enhanced QUIC logger that captures RTT metrics"""
    
    def __init__(self):
        super().__init__()
        self.connection = None
        
    def set_connection(self, connection):
        """Set the QUIC connection to extract metrics from"""
        self.connection = connection
        
    def log_metrics_event(self):
        """Log RTT and other metrics from the connection"""
        if self.connection is None:
            return
            
        try:
            # Extract metrics from the connection
            metrics = {}
            
            # Get RTT metrics if available
            if hasattr(self.connection, '_loss_detection'):
                loss_detector = self.connection._loss_detection
                if hasattr(loss_detector, 'latest_rtt'):
                    metrics["latest_rtt"] = getattr(loss_detector, 'latest_rtt', 0)
                if hasattr(loss_detector, 'smoothed_rtt'):
                    metrics["smoothed_rtt"] = getattr(loss_detector, 'smoothed_rtt', 0)
                if hasattr(loss_detector, 'rtt_variance'):
                    metrics["rtt_variance"] = getattr(loss_detector, 'rtt_variance', 0)
                if hasattr(loss_detector, 'min_rtt'):
                    metrics["min_rtt"] = getattr(loss_detector, 'min_rtt', 0)
            
            # Log the metrics event
            if metrics:
                self._log_event(
                    category="transport",
                    event="metrics_updated",
                    data={"metrics": metrics}
                )
        except Exception as e:
            print(f"Error logging metrics: {e}")

class VideoStreamProtocol(QuicConnectionProtocol):
    """QUIC Protocol with adaptive bitrate streaming and metrics"""
    
    def __init__(self, *args, stream_qlogger=None, metrics_calc=None, bitrates=None, segments_per_bitrate=4, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream_qlogger = stream_qlogger
        self.metrics_calc = metrics_calc
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
        self.segment_start_time = 0

    def get_next_stream_id(self) -> int:
        stream_id = self._quic.get_next_available_stream_id()
        print(f"Using stream ID: {stream_id}")
        return stream_id

    async def request_next_segment(self):
        if self.segment_index >= self.segments_per_bitrate:
            print("All segments completed!")
            return False

        # Determine video filename based on current bitrate
        if self.current_bitrate == 360:
            video_name = f"sample_low_seg{self.segment_index}.mp4"
        elif self.current_bitrate == 720:
            video_name = f"sample_medium_seg{self.segment_index}.mp4"
        else:  # 1080
            video_name = f"sample_high_seg{self.segment_index}.mp4"
        
        print(f"Requesting segment {self.segment_index} at {self.current_bitrate}p: {video_name}")
        
        self.current_stream_id = self.get_next_stream_id()
        self.video_data = b""
        self.received_bytes = 0
        self.transfer_complete.clear()
        self.segment_start_time = time.time()

        # Log stream request
        if self.stream_qlogger:
            self.stream_qlogger.log_stream_request(self.current_stream_id, video_name.encode())

        # Send GET request for segment
        request_data = f"GET {video_name}".encode()
        print(f"Sending request: {request_data} on stream {self.current_stream_id}")
        
        # Send request and immediately end the stream for request
        self._quic.send_stream_data(
            stream_id=self.current_stream_id,
            data=request_data,
            end_stream=True  # End stream after request
        )
        
        # Force transmission
        self.transmit()

        print(f"Waiting for video data on stream {self.current_stream_id}...")
        
        # Wait for transfer to complete with timeout
        try:
            await asyncio.wait_for(self.transfer_complete.wait(), timeout=30.0)
            self.last_chunk_time = time.time() - self.segment_start_time
            
            # Record metrics for completed segment
            if self.metrics_calc:
                metrics = self.metrics_calc.record_segment_metrics(
                    segment_index=self.segment_index,
                    bitrate=self.current_bitrate * 1000,  # Convert to bps
                    segment_size=self.received_bytes,
                    download_time=self.last_chunk_time,
                    timestamp=datetime.now().isoformat(),
                    is_complete=True
                )
                
                # Log metrics to qlog
                if self.stream_qlogger:
                    self.stream_qlogger.log_metrics(metrics)
                
                # Display metrics
                print(f"Metrics - Throughput: {metrics['throughput_bps']/1e6:.2f} Mbps, "
                      f"RTT: {metrics['rtt_estimate_sec']*1000:.1f} ms, "
                      f"Buffer: {metrics['buffer_level_sec']:.1f}s, "
                      f"Rebuffering: {metrics['is_rebuffering']}")
                      
        except asyncio.TimeoutError:
            print(f"Timeout waiting for segment {self.segment_index}")
            # Record failed segment metrics
            if self.metrics_calc:
                self.metrics_calc.record_segment_metrics(
                    segment_index=self.segment_index,
                    bitrate=self.current_bitrate * 1000,
                    segment_size=self.received_bytes,
                    download_time=30.0,  # timeout duration
                    timestamp=datetime.now().isoformat(),
                    is_complete=False
                )
            return False

        # Calculate throughput for ABR decision
        if self.last_chunk_time > 0:
            throughput_kbps = (self.received_bytes * 8) / self.last_chunk_time / 1000
        else:
            throughput_kbps = 0
            
        print(f"Segment {self.segment_index} finished: {self.received_bytes} bytes, {throughput_kbps:.2f} kbps, time: {self.last_chunk_time:.2f}s")

        # --- ORIGINAL ABR DECISION LOGIC (UNCHANGED) ---
        idx = self.bitrates.index(self.current_bitrate)
        if throughput_kbps > self.current_bitrate * 1.5 and idx < len(self.bitrates) - 1:
            self.current_bitrate = self.bitrates[idx + 1]
            print(f"⬆Switching UP to {self.current_bitrate}p")
        elif throughput_kbps < self.current_bitrate * 0.8 and idx > 0:
            self.current_bitrate = self.bitrates[idx - 1]
            print(f"⬇Switching DOWN to {self.current_bitrate}p")
        else:
            print(f"Keeping bitrate {self.current_bitrate}p")
        # --- END ORIGINAL ABR DECISION LOGIC ---

        self.segment_index += 1
        return True

    def quic_event_received(self, event):
        if not self.connection_established:
            self.connection_established = True
            if self.stream_qlogger:
                self.stream_qlogger.log_connection_established()
            print(f"Connection established after {(time.time() - self.start_time):.3f}s")

        if isinstance(event, StreamDataReceived):
            print(f"Client received data on stream {event.stream_id}, length: {len(event.data)}, end_stream: {event.end_stream}")
            
            if event.stream_id == self.current_stream_id:
                is_first_chunk = not self.video_data
                is_last_chunk = event.end_stream

                if is_first_chunk:
                    self.first_chunk_time = time.time() - self.start_time
                    print(f"First chunk received for stream {event.stream_id}")

                if self.stream_qlogger:
                    self.stream_qlogger.log_data_received(
                        event.stream_id, len(event.data),
                        is_first_chunk=is_first_chunk,
                        is_last_chunk=is_last_chunk
                    )

                # Record chunk-level metrics
                if self.metrics_calc:
                    self.metrics_calc.record_segment_metrics(
                        segment_index=self.segment_index,
                        bitrate=self.current_bitrate * 1000,
                        segment_size=len(event.data),
                        download_time=time.time() - self.segment_start_time,
                        timestamp=datetime.now().isoformat(),
                        is_complete=False
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
                    self.results_dir = Path('results')
                    self.results_dir.mkdir(exist_ok=True)
                    chunk_filename = self.results_dir / f"quic_received_{self.current_bitrate}p_seg{self.segment_index}.mp4"
                    with open(chunk_filename, "wb") as f:
                        f.write(self.video_data)
                    print(f"Segment saved: {chunk_filename} ({self.received_bytes} bytes)")

                    self.transfer_complete.set()
                    print(f"Transfer complete for stream {event.stream_id}")

        elif isinstance(event, DatagramFrameReceived):
            pass  # Ignore datagram frames

class VideoStreamClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        
        # ENHANCED CONFIGURATION WITH METRICS
        self.configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=["video-stream"],
            max_datagram_frame_size=65536,
            verify_mode=False,
            max_data=10485760,  # 10MB
            max_stream_data=1048576,  # 1MB per stream
            # Enable congestion control with metrics
            congestion_control_algorithm="reno",  # or "cubic"
        )

        # USE ENHANCED LOGGER
        self.packet_logger = DetailedQuicLogger()
        self.configuration.quic_logger = self.packet_logger
        self.stream_logger = StreamQLogger()
        self.metrics_calc = MetricsCalculator()

    async def run(self):
        print(f"Connecting to {self.host}:{self.port}...")
        print("RTT metrics logging ENABLED - collecting detailed connection metrics")
        
        self.stream_logger.log_connection_start(self.host, self.port)
        
        try:
            async with connect(
                host=self.host,
                port=self.port,
                configuration=self.configuration,
                create_protocol=lambda *args, **kwargs: VideoStreamProtocol(
                    *args, 
                    stream_qlogger=self.stream_logger,
                    metrics_calc=self.metrics_calc,
                    **kwargs
                )
            ) as protocol:
                print("Connected, starting ABR streaming with RTT monitoring...")
                
                segment_count = 0
                while await protocol.request_next_segment():
                    segment_count += 1
                    print(f"Successfully completed segment {segment_count}")
                    await asyncio.sleep(0.5)
                
                print(f"Streaming completed! Total segments: {segment_count}")
        
        except Exception as e:
            print(f"Connection error: {e}")
            import traceback
            traceback.print_exc()
        
        # Save all logs and metrics
        self.stream_logger.save_qlog('abr_video_with_rtt')
        self.metrics_calc.generate_summary_report()

        Path("qlog").mkdir(exist_ok=True)
        packet_log_file = Path("qlog") / f"packet_trace_with_rtt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.qlog"
        
        with open(packet_log_file, "w") as f:
            json.dump(self.packet_logger.to_dict(), f, indent=2)

        print(f"Enhanced Qlog with RTT saved to: {packet_log_file}")
        print(f"QUIC metrics saved to: {self.metrics_calc.metrics_file}")
        
        # Verify RTT data was captured
        self._verify_rtt_metrics(packet_log_file)

    def _verify_rtt_metrics(self, qlog_file):
        """Verify that RTT metrics were captured"""
        try:
            with open(qlog_file, 'r') as f:
                qlog_data = json.load(f)
            
            rtt_events = 0
            for event in qlog_data.get('traces', [{}])[0].get('events', []):
                if (len(event) >= 4 and 
                    event[1] == "transport" and 
                    event[2] == "metrics_updated"):
                    rtt_events += 1
                    metrics = event[3].get("metrics", {})
                    if "latest_rtt" in metrics:
                        print(f"✅ RTT metrics found: latest_rtt = {metrics['latest_rtt']}ms")
            
            if rtt_events > 0:
                print(f"Successfully captured {rtt_events} RTT measurement events")
            else:
                print("No RTT metrics found in qlog")
                
        except Exception as e:
            print(f"Error verifying RTT metrics: {e}")

async def main():
    client = VideoStreamClient("10.0.0.1", 4433)
    await client.run()


if __name__ == "__main__":
    print("Starting QUIC Video Streaming Client with Enhanced Metrics...")
    asyncio.run(main())