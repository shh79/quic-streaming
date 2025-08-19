import requests
from pydash import dash_parser
import time
import math

class DashVideoDownloader:
    def __init__(self, manifest_url):
        self.manifest_url = manifest_url
        self.manifest = None
        self.current_quality = 0
        self.download_history = []
        
    def fetch_manifest(self):
        """Download and parse the DASH manifest"""
        response = requests.get(self.manifest_url)
        self.manifest = dash_parser.parse(response.content)
        
    def get_available_bitrates(self):
        """Return available bitrates sorted from lowest to highest"""
        if not self.manifest:
            self.fetch_manifest()
            
        video_adaptations = [a for a in self.manifest.periods[0].adaptation_sets 
                            if a.content_type == "video"]
        representations = video_adaptations[0].representations
        return sorted([(r.bandwidth, r.id) for r in representations], key=lambda x: x[0])
    
    def calculate_current_bitrate(self, segment_size, download_time):
        """Calculate current network bitrate in bits per second"""
        if download_time == 0:
            return 0
        return (segment_size * 8) / download_time  # Convert bytes to bits
    
    def get_network_condition(self):
        """Estimate network condition based on download history"""
        if not self.download_history:
            return "unknown"
            
        # Use average of last 3 downloads
        recent = self.download_history[-3:]
        avg_bitrate = sum(b for b, _ in recent) / len(recent)
        
        if avg_bitrate < 500000:  # 500 kbps
            return "poor"
        elif avg_bitrate < 2000000:  # 2 Mbps
            return "moderate"
        else:
            return "good"
    
    def select_quality(self):
        """Select appropriate quality based on network conditions"""
        available_qualities = self.get_available_bitrates()
        condition = self.get_network_condition()
        
        if condition == "poor":
            return 0  # lowest quality
        elif condition == "moderate":
            return len(available_qualities) // 2  # middle quality
        else:
            return len(available_qualities) - 1  # highest quality
    
    def download_segment(self, representation_id, segment_url):
        """Download a single segment and measure performance"""
        start_time = time.time()
        response = requests.get(segment_url)
        download_time = time.time() - start_time
        
        segment_size = len(response.content)
        bitrate = self.calculate_current_bitrate(segment_size, download_time)
        
        # Store this download's metrics
        self.download_history.append((bitrate, download_time))
        
        return response.content
    
    def download_video(self, output_file, duration=60):
        """Download video segments with adaptive quality"""
        if not self.manifest:
            self.fetch_manifest()
            
        video_adaptations = [a for a in self.manifest.periods[0].adaptation_sets 
                           if a.content_type == "video"][0]
        
        # Get initial segments
        available_qualities = self.get_available_bitrates()
        self.current_quality = self.select_quality()
        representation_id = available_qualities[self.current_quality][1]
        
        with open(output_file, 'wb') as f:
            segment_number = 0
            start_time = time.time()
            
            while time.time() - start_time < duration:
                # Find the representation
                representation = next(r for r in video_adaptations.representations 
                                    if r.id == representation_id)
                
                # Get segment URL (simplified - real implementation needs to handle template URLs)
                segment_url = representation.base_url + f"seg-{segment_number}.m4s"
                
                try:
                    segment_data = self.download_segment(representation_id, segment_url)
                    f.write(segment_data)
                    segment_number += 1
                    
                    # Periodically check if we should switch quality
                    if segment_number % 3 == 0:
                        new_quality = self.select_quality()
                        if new_quality != self.current_quality:
                            self.current_quality = new_quality
                            representation_id = available_qualities[self.current_quality][1]
                            print(f"Switching to quality {representation_id} with bitrate {available_qualities[self.current_quality][0]}")
                
                except Exception as e:
                    print(f"Error downloading segment: {e}")
                    # Try downgrading quality
                    if self.current_quality > 0:
                        self.current_quality -= 1
                        representation_id = available_qualities[self.current_quality][1]
                        print(f"Downgrading to quality {representation_id} due to error")

        print("Download completed")

# Usage example
if __name__ == "__main__":
    manifest_url = "http://10.0.0.2:8080/manifest.mpd"
    downloader = DashVideoDownloader(manifest_url)
    downloader.download_video("dash_output.mp4", duration=30)  # Download 30 seconds of video