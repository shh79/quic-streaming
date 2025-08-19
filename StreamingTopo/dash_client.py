import requests
import time
import random
from collections import deque

class DASHClient:
    def __init__(self, manifest_url):
        self.manifest_url = manifest_url
        self.bitrates = ['low', 'medium', 'high']  # Ordered from lowest to highest
        self.current_bitrate = 'medium'  # Start with medium quality
        self.buffer = deque()
        self.buffer_capacity = 3  # Buffer capacity in segments
        self.download_history = deque(maxlen=5)  # Track last 5 download times
        
    def fetch_manifest(self):
        response = requests.get(self.manifest_url)
        return response.text
    
    def download_segment(self, segment_url):
        start_time = time.time()
        response = requests.get(segment_url, stream=True)
        content = response.content
        download_time = time.time() - start_time
        
        # Calculate bandwidth (assuming we know the segment size)
        segment_size = len(content)
        bandwidth = segment_size * 8 / download_time  # bits per second
        
        self.download_history.append(bandwidth)
        return content, download_time
    
    def estimate_bandwidth(self):
        if not self.download_history:
            return 1000000  # Default to 1 Mbps if no history
        
        # Simple moving average of bandwidth
        return sum(self.download_history) / len(self.download_history)
    
    def select_bitrate(self):
        available_bandwidth = self.estimate_bandwidth()
        
        # Simple bitrate adaptation logic
        if available_bandwidth > 1500000:  # 1.5 Mbps
            return 'high'
        elif available_bandwidth > 750000:  # 0.75 Mbps
            return 'medium'
        else:
            return 'low'
    
    def play_video(self):
        print("Fetching manifest...")
        mpd = self.fetch_manifest()
        print("Manifest loaded. Starting playback...")
        
        segment_num = 1
        while segment_num <= 10:  # Play 10 segments
            # Check buffer level
            if len(self.buffer) >= self.buffer_capacity:
                # Play from buffer
                segment = self.buffer.popleft()
                print(f"Playing segment {segment_num} at {self.current_bitrate} quality")
                time.sleep(3)  # Simulate playback time (3-second segments)
                segment_num += 1
                continue
            
            # Adapt bitrate based on current conditions
            self.current_bitrate = self.select_bitrate()
            
            # Download next segment
            segment_url = f"http://10.0.0.2:8080/segment_{segment_num}_.mp4"
            print(f"Downloading segment {segment_num} at {self.current_bitrate} quality...")
            
            segment, download_time = self.download_segment(segment_url)
            print(f"Downloaded in {download_time:.2f}s")
            
            # Add to buffer
            self.buffer.append(segment)
            
            # Simulate network variability
            time.sleep(random.uniform(0.1, 0.3))

if __name__ == '__main__':
    client = DASHClient("http://10.0.0.2:8080/manifest.mpd")
    client.play_video()