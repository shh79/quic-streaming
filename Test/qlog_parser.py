import json
import pandas as pd
from pathlib import Path

class QLogParser:
    def __init__(self):
        self.metrics = {}
    
    def parse_qlog_file(self, qlog_path):
        """Parse QLog file and extract real metrics"""
        try:
            with open(qlog_path, 'r') as f:
                qlog_data = json.load(f)
            
            events = qlog_data.get('trace', {}).get('events', [])
            
            # Extract connection metrics
            connection_events = [e for e in events if 'connection' in e.get('name', '')]
            stream_events = [e for e in events if 'stream' in e.get('name', '')]
            transport_events = [e for e in events if 'transport' in e.get('name', '')]
            
            metrics = {
                'startup_delay': self.extract_startup_delay(stream_events),
                'throughput_timeline': self.extract_throughput_timeline(stream_events),
                'rtt_timeline': self.extract_rtt_timeline(transport_events),
                'packet_loss': self.extract_packet_loss(transport_events),
                'total_bytes_transferred': self.extract_total_bytes(stream_events),
            }
            
            return metrics
            
        except Exception as e:
            print(f"Error parsing QLog {qlog_path}: {e}")
            return {}
    
    def extract_startup_delay(self, stream_events):
        """Extract startup delay from stream events"""
        first_data = None
        connection_start = None
        
        for event in stream_events:
            if 'start' in event.get('name', ''):
                connection_start = event.get('time', 0)
            elif 'data_received' in event.get('name', '') and event.get('data', {}).get('is_first_chunk'):
                first_data = event.get('time', 0)
                break
        
        if connection_start and first_data:
            return (first_data - connection_start) / 1000  # Convert to seconds
        return 0
    
    def extract_throughput_timeline(self, stream_events):
        """Extract throughput timeline"""
        throughput_data = []
        cumulative_bytes = 0
        
        data_events = [e for e in stream_events if 'data_received' in e.get('name', '')]
        
        for event in data_events:
            time_ms = event.get('time', 0)
            bytes_received = event.get('data', {}).get('bytes_received', 0)
            cumulative_bytes += bytes_received
            
            if time_ms > 0:
                throughput_kbps = (cumulative_bytes * 8) / (time_ms / 1000) / 1024  # kbps
                throughput_data.append({
                    'time': time_ms / 1000,
                    'throughput_kbps': throughput_kbps,
                    'instant_throughput': (bytes_received * 8) / 1000  # kbps
                })
        
        return throughput_data
    
    def extract_rtt_timeline(self, transport_events):
        """Extract RTT timeline from transport events"""
        rtt_events = [e for e in transport_events if 'rtt' in e.get('name', '').lower()]
        rtt_data = []
        
        for event in rtt_events:
            rtt_data.append({
                'time': event.get('time', 0) / 1000,
                'rtt': event.get('data', {}).get('rtt_ms', 0)
            })
        
        return rtt_data
    
    def extract_packet_loss(self, transport_events):
        """Extract packet loss information"""
        loss_events = [e for e in transport_events if 'loss' in e.get('name', '').lower()]
        return len(loss_events)
    
    def extract_total_bytes(self, stream_events):
        """Extract total bytes transferred"""
        total_bytes = 0
        for event in stream_events:
            if 'data_received' in event.get('name', ''):
                total_bytes += event.get('data', {}).get('bytes_received', 0)
        return total_bytes

# Usage
def parse_all_qlogs(results_dir="results"):
    parser = QLogParser()
    qlog_files = list(Path(results_dir).glob('**/*.qlog'))
    
    all_metrics = {}
    for qlog_file in qlog_files:
        metrics = parser.parse_qlog_file(qlog_file)
        all_metrics[qlog_file.name] = metrics
    
    return all_metrics