import requests
import xml.etree.ElementTree as ET
import os
import time
import math
import csv
from datetime import datetime
from collections import deque

# Config
MPD_URL = "http://10.0.0.2:8080/manifest.mpd"
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

class MetricsCalculator:
    def __init__(self, segment_duration=2.0):  # Assuming 2-second segments
        self.segment_duration = segment_duration
        
        # Metrics storage
        self.download_times = []
        self.throughput_history = deque(maxlen=5)  # Last 5 segments for moving average
        self.buffer_level = 0.0  # in seconds
        self.rebuffering_count = 0
        self.rebuffering_start_time = None
        self.total_rebuffering_duration = 0.0
        self.playback_position = 0.0
        self.last_download_time = None
        
        # Real-time metrics tracking
        self.current_bitrate = 0
        self.bitrate_history = []
        self.segment_metrics = []
        
        # Create metrics CSV file
        self.metrics_file = os.path.join(RESULTS_DIR, f"dash_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        self._initialize_metrics_file()

    def _initialize_metrics_file(self):
        """Initialize CSV file with headers"""
        with open(self.metrics_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'segment_index', 'representation_id', 'bitrate_bps',
                'segment_size_bytes', 'download_time_sec', 'throughput_bps',
                'smoothed_throughput_bps', 'rtt_sec', 'buffer_level_sec',
                'rebuffering_count', 'total_rebuffering_duration_sec',
                'playback_position_sec', 'is_rebuffering'
            ])

    def calculate_rtt(self, download_time):
        """Calculate Round Trip Time (approximated from download time)"""
        # Using download time as approximate RTT
        rtt = download_time
        self.download_times.append(rtt)
        return rtt

    def calculate_throughput(self, data_size, download_time):
        """Calculate throughput in bits per second"""
        if download_time <= 0:
            return 0
            
        throughput = (data_size * 8) / download_time  # bits/sec
        self.throughput_history.append(throughput)
        return throughput

    def get_smoothed_throughput(self):
        """Get moving average throughput"""
        if not self.throughput_history:
            return 0
        return sum(self.throughput_history) / len(self.throughput_history)

    def update_buffer(self, download_time, segment_duration):
        """Update buffer level and track rebuffering"""
        was_rebuffering = False
        
        # Check if rebuffering occurred
        if self.buffer_level <= 0:
            if self.rebuffering_start_time is None:
                self.rebuffering_start_time = time.time()
                self.rebuffering_count += 1
                was_rebuffering = True
        else:
            # Normal playback - consume buffer
            self.buffer_level = max(0, self.buffer_level - download_time)
        
        # Add new segment to buffer
        self.buffer_level += segment_duration
        
        # Update rebuffering duration
        if self.rebuffering_start_time is not None and self.buffer_level > 0:
            rebuffering_duration = time.time() - self.rebuffering_start_time
            self.total_rebuffering_duration += rebuffering_duration
            self.rebuffering_start_time = None
        
        return was_rebuffering

    def record_metrics(self, segment_index, rep_id, bitrate, segment_size, 
                      download_time, timestamp):
        """Record all metrics for current segment"""
        
        # Calculate metrics
        throughput = self.calculate_throughput(segment_size, download_time)
        smoothed_throughput = self.get_smoothed_throughput()
        rtt = self.calculate_rtt(download_time)
        
        # Update buffer and check for rebuffering
        is_rebuffering = self.update_buffer(download_time, self.segment_duration)
        
        # Update playback position
        self.playback_position = segment_index * self.segment_duration
        
        # Store current metrics
        metrics = {
            'timestamp': timestamp,
            'segment_index': segment_index,
            'representation_id': rep_id,
            'bitrate_bps': bitrate,
            'segment_size_bytes': segment_size,
            'download_time_sec': download_time,
            'throughput_bps': throughput,
            'smoothed_throughput_bps': smoothed_throughput,
            'rtt_sec': rtt,
            'buffer_level_sec': self.buffer_level,
            'rebuffering_count': self.rebuffering_count,
            'total_rebuffering_duration_sec': self.total_rebuffering_duration,
            'playback_position_sec': self.playback_position,
            'is_rebuffering': is_rebuffering
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
                metrics['representation_id'],
                metrics['bitrate_bps'],
                metrics['segment_size_bytes'],
                metrics['download_time_sec'],
                metrics['throughput_bps'],
                metrics['smoothed_throughput_bps'],
                metrics['rtt_sec'],
                metrics['buffer_level_sec'],
                metrics['rebuffering_count'],
                metrics['total_rebuffering_duration_sec'],
                metrics['playback_position_sec'],
                metrics['is_rebuffering']
            ])

    def generate_summary_report(self):
        """Generate a summary report of all metrics"""
        summary_file = os.path.join(RESULTS_DIR, f"dash_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        
        with open(summary_file, 'w') as f:
            f.write("=== DASH Streaming Metrics Summary ===\n")
            f.write(f"Total segments downloaded: {len(self.segment_metrics)}\n")
            f.write(f"Total rebuffering events: {self.rebuffering_count}\n")
            f.write(f"Total rebuffering duration: {self.total_rebuffering_duration:.2f} seconds\n")
            f.write(f"Average throughput: {sum(m['throughput_bps'] for m in self.segment_metrics) / len(self.segment_metrics) / 1e6:.2f} Mbps\n")
            f.write(f"Average RTT: {sum(m['rtt_sec'] for m in self.segment_metrics) / len(self.segment_metrics):.3f} seconds\n")
            f.write(f"Maximum buffer level: {max(m['buffer_level_sec'] for m in self.segment_metrics):.2f} seconds\n")
            
            # Bitrate switching analysis
            bitrate_changes = sum(1 for i in range(1, len(self.bitrate_history)) 
                                if self.bitrate_history[i] != self.bitrate_history[i-1])
            f.write(f"Bitrate switches: {bitrate_changes}\n")
        
        print(f"📊 Summary report saved: {summary_file}")

print("Fetching manifest...")
resp = requests.get(MPD_URL)
resp.raise_for_status()
mpd_content = resp.text

root = ET.fromstring(mpd_content)
ns = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}

# Parse representations
representations = []
for rep in root.findall(".//mpd:Representation", ns):
    rep_id = rep.attrib["id"]
    bw = int(rep.attrib["bandwidth"])
    base_url = rep.find("mpd:BaseURL", ns).text
    seg_list = rep.find("mpd:SegmentList", ns)
    init_url = seg_list.find("mpd:Initialization", ns).attrib["sourceURL"]
    seg_urls = [seg.attrib["media"] for seg in seg_list.findall("mpd:SegmentURL", ns)]
    representations.append({
        "id": rep_id,
        "bandwidth": bw,
        "base_url": base_url,
        "init": init_url,
        "segments": seg_urls
    })

# Sort representations by bitrate (low → high)
representations.sort(key=lambda r: r["bandwidth"])

# Initialize metrics calculator
metrics_calc = MetricsCalculator(segment_duration=2.0)  # Adjust based on your content

# Start with lowest quality
current_rep = representations[0]
print(f"Starting with {current_rep['id']} ({current_rep['bandwidth']} bps)")

base_path = MPD_URL.rsplit("/", 1)[0] + "/"
num_segments = max(len(r["segments"]) for r in representations)

# Download initialization segment first
print("Downloading initialization segment...")
init_url = base_path + current_rep["base_url"] + current_rep["init"]
init_start = time.time()
init_data = requests.get(init_url).content
init_time = time.time() - init_start

init_metrics = metrics_calc.record_metrics(
    segment_index=0,
    rep_id="init",
    bitrate=current_rep["bandwidth"],
    segment_size=len(init_data),
    download_time=init_time,
    timestamp=datetime.now().isoformat()
)

for i in range(num_segments):
    # Safety: pick segment from current_rep if exists
    if i >= len(current_rep["segments"]):
        continue
        
    seg_name = current_rep["segments"][i]
    seg_url = base_path + current_rep["base_url"] + seg_name
    seg_filename = os.path.join(RESULTS_DIR, f"dash_{i}_{current_rep['id']}_{seg_name}")

    print(f"Downloading segment {i} from {current_rep['id']} -> {seg_filename}")
    
    # Download segment and measure time
    start_time = time.time()
    data = requests.get(seg_url).content
    download_time = time.time() - start_time
    
    # Calculate and record metrics
    metrics = metrics_calc.record_metrics(
        segment_index=i + 1,  # +1 because init was segment 0
        rep_id=current_rep['id'],
        bitrate=current_rep['bandwidth'],
        segment_size=len(data),
        download_time=download_time,
        timestamp=datetime.now().isoformat()
    )
    
    # Save segment
    with open(seg_filename, "wb") as f:
        f.write(data)

    # Display current metrics
    print(f"  size={len(data)/1024:.1f} KB, time={download_time:.2f}s, "
          f"throughput={metrics['throughput_bps']/1e6:.2f} Mbps, "
          f"buffer={metrics['buffer_level_sec']:.1f}s, "
          f"rebuffering={metrics['is_rebuffering']}")

    # --- Adaptive bitrate logic ---
    safety_factor = 0.8
    suitable_reps = [r for r in representations if r["bandwidth"] < metrics['smoothed_throughput_bps'] * safety_factor]
    if suitable_reps:
        new_rep = suitable_reps[-1]  # pick highest suitable
    else:
        new_rep = representations[0]

    if new_rep["id"] != current_rep["id"]:
        print(f"⚡ Switching {current_rep['id']} -> {new_rep['id']}")
        current_rep = new_rep
        metrics_calc.bitrate_history.append(new_rep["bandwidth"])

print(f"✅ All segments saved in folder: {RESULTS_DIR}")
print(f"📈 Metrics saved to: {metrics_calc.metrics_file}")

# Generate final summary
metrics_calc.generate_summary_report()

# Print final statistics
print(f"\n📊 Final Statistics:")
print(f"   Total rebuffering events: {metrics_calc.rebuffering_count}")
print(f"   Total rebuffering time: {metrics_calc.total_rebuffering_duration:.2f}s")
print(f"   Average throughput: {sum(m['throughput_bps'] for m in metrics_calc.segment_metrics) / len(metrics_calc.segment_metrics) / 1e6:.2f} Mbps")
print(f"   Maximum buffer level: {max(m['buffer_level_sec'] for m in metrics_calc.segment_metrics):.2f}s")