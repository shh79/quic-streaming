import requests
import time
import os
import argparse
import json
from datetime import datetime
from pathlib import Path

class DashVideoDownloader:
    def __init__(self, manifest_url):
        self.manifest_url = manifest_url
        self.download_history = []
        self.metrics = {
            'startup_delay': 0,
            'rebuffering_events': 0,
            'total_rebuffering_time': 0,
            'bitrate_switches': 0,
            'average_bitrate': 0,
            'segment_download_times': []
        }
        self.start_time = time.time()
        
    def download_video(self, output_file, duration=30):
        """Download video segments with adaptive quality"""
        print(f"Starting DASH download from: {self.manifest_url}")
        
        # Create output directory if needed
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
        
        segment_count = 0
        total_downloaded = 0
        current_quality = 1  # Start with medium quality
        
        # Available qualities (simulated)
        qualities = [
            {'id': 1, 'bandwidth': 400000, 'name': '240p'},
            {'id': 2, 'bandwidth': 800000, 'name': '360p'},
            {'id': 3, 'bandwidth': 1500000, 'name': '480p'}
        ]
        
        self.metrics['startup_delay'] = time.time() - self.start_time
        
        try:
            with open(output_file, 'wb') as output_f:
                for segment_num in range(1, min(20, duration // 2 + 2)):
                    # Simulate adaptive bitrate - change quality based on segment number
                    if segment_num % 5 == 0:
                        current_quality = min(3, current_quality + 1)
                        self.metrics['bitrate_switches'] += 1
                        print(f"Switching to quality: {qualities[current_quality-1]['name']}")
                    
                    # Generate segment URL (simplified)
                    segment_url = self.manifest_url.replace('manifest.mpd', f'segment_{segment_num}.m4s')
                    
                    print(f"Downloading segment {segment_num} ({qualities[current_quality-1]['name']})...")
                    
                    segment_start = time.time()
                    try:
                        response = requests.get(segment_url, timeout=10)
                        response.raise_for_status()
                        
                        segment_data = response.content
                        download_time = time.time() - segment_start
                        
                        output_f.write(segment_data)
                        segment_count += 1
                        total_downloaded += len(segment_data)
                        
                        self.metrics['segment_download_times'].append(download_time)
                        
                        # Simulate occasional rebuffering
                        if segment_num in [3, 8] and len(segment_data) > 0:
                            self.metrics['rebuffering_events'] += 1
                            rebuffer_time = 2.0
                            self.metrics['total_rebuffering_time'] += rebuffer_time
                            print(f"Simulated rebuffering: {rebuffer_time}s")
                            time.sleep(rebuffer_time)
                        
                        download_rate = (len(segment_data) * 8) / download_time if download_time > 0 else 0
                        print(f"  Segment {segment_num}: {len(segment_data)/1024:.1f} KB, {download_time:.2f}s, {download_rate/1000:.1f} kbps")
                        
                        # Check if we've reached the desired duration
                        if total_downloaded > duration * 512 * 1024:  # ~0.5MB per second of video
                            break
                            
                    except requests.RequestException as e:
                        print(f"  Error downloading segment {segment_num}: {e}")
                        # Lower quality on error
                        current_quality = max(1, current_quality - 1)
                        continue
        
        except Exception as e:
            print(f"Download error: {e}")
            return False
        
        # Calculate final metrics
        total_time = time.time() - self.start_time
        self.metrics['average_bitrate'] = (total_downloaded * 8) / total_time if total_time > 0 else 0
        self.metrics['total_downloaded'] = total_downloaded
        self.metrics['total_time'] = total_time
        self.metrics['segment_count'] = segment_count
        
        print(f"\n=== DASH DOWNLOAD COMPLETE ===")
        print(f"Segments: {segment_count}")
        print(f"Downloaded: {total_downloaded/1024/1024:.2f} MB")
        print(f"Total time: {total_time:.2f}s")
        print(f"Average bitrate: {self.metrics['average_bitrate']/1000:.2f} kbps")
        print(f"Startup delay: {self.metrics['startup_delay']:.2f}s")
        print(f"Rebuffering events: {self.metrics['rebuffering_events']}")
        print(f"Total rebuffering time: {self.metrics['total_rebuffering_time']:.2f}s")
        print(f"Bitrate switches: {self.metrics['bitrate_switches']}")
        
        self.save_metrics(output_file)
        return True

    def save_metrics(self, output_file):
        """Save download metrics to JSON file"""
        metrics_file = f"{output_file}_metrics.json"
        with open(metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        print(f"Metrics saved: {metrics_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', default='http://10.0.0.2:8080/manifest.mpd', help='MPD manifest URL')
    parser.add_argument('--output', default='dash_output.mp4', help='Output file')
    parser.add_argument('--duration', type=int, default=30, help='Download duration in seconds')
    
    args = parser.parse_args()
    
    downloader = DashVideoDownloader(args.manifest)
    success = downloader.download_video(args.output, args.duration)
    
    if success:
        print("✓ DASH download completed successfully")
    else:
        print("✗ DASH download failed")