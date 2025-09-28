import requests
import xml.etree.ElementTree as ET
import time
import os
import argparse
import json
from datetime import datetime
from pathlib import Path

class DashVideoDownloader:
    def __init__(self, manifest_url, abr_algorithm='throughput', buffer_target=15):
        self.manifest_url = manifest_url
        self.manifest = None
        self.current_quality = 0
        self.download_history = []
        self.abr_algorithm = abr_algorithm
        self.buffer_target = buffer_target
        self.buffer_level = 0
        self.metrics = {
            'startup_delay': 0,
            'rebuffering_events': 0,
            'total_rebuffering_time': 0,
            'bitrate_switches': 0,
            'average_bitrate': 0,
            'segment_download_times': []
        }
        self.start_time = time.time()
        
    def fetch_manifest(self):
        """Download and parse the DASH manifest"""
        try:
            response = requests.get(self.manifest_url, timeout=10)
            response.raise_for_status()
            self.manifest = self.parse_mpd(response.content)
            return True
        except Exception as e:
            print(f"Error fetching manifest: {e}")
            return False
        
    def get_available_bitrates(self):
        """Return available bitrates sorted from lowest to highest"""
        if not self.manifest:
            if not self.fetch_manifest():
                return []
                
        video_reps = []
        for period in self.manifest['periods']:
            for adapt_set in period['adaptation_sets']:
                content_types = [comp.get('content_type', '') 
                               for comp in adapt_set.get('content_components', [])]
                if any('video' in ct.lower() for ct in content_types):
                    for rep in adapt_set.get('representations', []):
                        video_reps.append((rep.get('bandwidth', 0), rep.get('id', ''), rep))
        
        return sorted(video_reps, key=lambda x: x[0])
    
    def calculate_current_bitrate(self, segment_size, download_time):
        """Calculate current network bitrate in bits per second"""
        if download_time == 0:
            return 0
        return (segment_size * 8) / download_time
    
    def get_network_condition(self):
        """Estimate network condition based on download history"""
        if not self.download_history:
            return "unknown"
            
        recent = self.download_history[-3:] if len(self.download_history) >= 3 else self.download_history
        avg_bitrate = sum(b for b, _ in recent) / len(recent) if recent else 0
        
        if avg_bitrate < 500000:  # 500 kbps
            return "poor"
        elif avg_bitrate < 2000000:  # 2 Mbps
            return "moderate"
        else:
            return "good"
    
    def select_quality_throughput_based(self):
        """Throughput-based ABR algorithm"""
        available_qualities = self.get_available_bitrates()
        if not available_qualities:
            return 0
            
        # Use average of recent throughput
        recent = self.download_history[-5:] if len(self.download_history) >= 5 else self.download_history
        avg_throughput = sum(b for b, _ in recent) / len(recent) if recent else available_qualities[0][0]
        
        # Select highest quality that is <= 80% of average throughput
        for i, (bitrate, _, _) in enumerate(available_qualities):
            if bitrate <= avg_throughput * 0.8:
                selected = i
            else:
                break
        else:
            selected = len(available_qualities) - 1
            
        return selected
    
    def select_quality_buffer_based(self):
        """Buffer-based ABR algorithm (BBA)"""
        available_qualities = self.get_available_bitrates()
        if not available_qualities:
            return 0
            
        if self.buffer_level < 5:  # Very low buffer
            return 0  # Lowest quality
        elif self.buffer_level < 10:  # Low buffer
            return len(available_qualities) // 3  # Low quality
        elif self.buffer_level < 15:  # Medium buffer
            return len(available_qualities) // 2  # Medium quality
        else:  # High buffer
            return len(available_qualities) - 1  # Highest quality
    
    def select_quality_hybrid(self):
        """Hybrid ABR algorithm"""
        throughput_based = self.select_quality_throughput_based()
        buffer_based = self.select_quality_buffer_based()
        
        # Weighted combination
        buffer_weight = min(self.buffer_level / self.buffer_target, 1.0)
        return int(throughput_based * (1 - buffer_weight) + buffer_based * buffer_weight)
    
    def select_quality_index(self):
        """Select quality based on configured ABR algorithm"""
        if self.abr_algorithm == 'throughput':
            return self.select_quality_throughput_based()
        elif self.abr_algorithm == 'buffer':
            return self.select_quality_buffer_based()
        elif self.abr_algorithm == 'hybrid':
            return self.select_quality_hybrid()
        else:
            return self.select_quality_throughput_based()

    def get_representation_by_index(self, quality_index):
        """Get representation by quality index"""
        available_qualities = self.get_available_bitrates()
        if 0 <= quality_index < len(available_qualities):
            return available_qualities[quality_index][2]
        return available_qualities[-1][2] if available_qualities else None

    def download_segment(self, segment_url):
        """Download a single segment and measure performance"""
        start_time = time.time()
        try:
            response = requests.get(segment_url, stream=True, timeout=30)
            response.raise_for_status()
            
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
            
            download_time = time.time() - start_time
            segment_size = len(content)
            bitrate = self.calculate_current_bitrate(segment_size, download_time)
            
            self.download_history.append((bitrate, download_time))
            self.metrics['segment_download_times'].append(download_time)
            
            return content, download_time, True
            
        except Exception as e:
            print(f"Error downloading segment: {e}")
            return None, time.time() - start_time, False

    def download_video(self, output_file, duration=60, segment_length=4):
        """Download video segments with adaptive quality"""
        if not self.fetch_manifest():
            return False
        
        available_qualities = self.get_available_bitrates()
        if not available_qualities:
            print("No video representations found")
            return False
        
        print(f"Available qualities: {[(q[0]//1000, q[1]) for q in available_qualities]}")
        print(f"Using ABR algorithm: {self.abr_algorithm}")
        
        current_quality_index = len(available_qualities) // 2
        segment_count = 0
        total_downloaded = 0
        last_quality = current_quality_index
        rebuffering_start = None
        
        self.metrics['startup_delay'] = time.time() - self.start_time
        
        with open(output_file, 'wb') as output_f:
            for segment_num in range(1, min(100, duration // segment_length + 2)):
                # Update buffer level (simulated)
                self.buffer_level = max(0, self.buffer_level - segment_length)
                if self.buffer_level == 0 and rebuffering_start is None:
                    rebuffering_start = time.time()
                    self.metrics['rebuffering_events'] += 1
                    print("BUFFERING...")
                
                # Select quality
                current_quality_index = self.select_quality_index()
                if current_quality_index != last_quality:
                    self.metrics['bitrate_switches'] += 1
                    last_quality = current_quality_index
                
                representation = self.get_representation_by_index(current_quality_index)
                if not representation:
                    break
                
                base_url = representation.get('base_url', '')
                if not base_url:
                    break
                
                # Make URL absolute if relative
                if not base_url.startswith(('http://', 'https://')):
                    base_dir = '/'.join(self.manifest_url.split('/')[:-1]) + '/'
                    base_url = base_dir + base_url
                
                # Generate segment URL
                segment_url = self.generate_segment_url(base_url, segment_num)
                
                print(f"Segment {segment_num}: Quality {current_quality_index} "
                      f"({representation.get('bandwidth', 0)//1000} kbps), "
                      f"Buffer: {self.buffer_level:.1f}s")
                
                segment_data, download_time, success = self.download_segment(segment_url)
                
                if success and segment_data:
                    output_f.write(segment_data)
                    segment_count += 1
                    total_downloaded += len(segment_data)
                    
                    # Update buffer
                    self.buffer_level += segment_length
                    if rebuffering_start is not None and self.buffer_level > 2:
                        rebuffering_time = time.time() - rebuffering_start
                        self.metrics['total_rebuffering_time'] += rebuffering_time
                        rebuffering_start = None
                        print(f"Buffering ended after {rebuffering_time:.2f}s")
                    
                    # Print network status
                    if self.download_history:
                        recent_bitrate = self.download_history[-1][0]
                        condition = self.get_network_condition()
                        print(f"  Network: {recent_bitrate/1000000:.2f} Mbps, Condition: {condition}")
                    
                    # Check duration
                    if total_downloaded > duration * 1024 * 1024:
                        break
                else:
                    print(f"  Download failed, retrying with lower quality")
                    current_quality_index = max(0, current_quality_index - 1)
                    time.sleep(1)
        
        # Calculate final metrics
        total_time = time.time() - self.start_time
        self.metrics['average_bitrate'] = (total_downloaded * 8) / total_time if total_time > 0 else 0
        self.metrics['total_downloaded'] = total_downloaded
        self.metrics['total_time'] = total_time
        self.metrics['segment_count'] = segment_count
        
        print(f"\n=== DASH Download Complete ===")
        print(f"Segments: {segment_count}, Downloaded: {total_downloaded/1024/1024:.2f} MB")
        print(f"Total time: {total_time:.2f}s, Average bitrate: {self.metrics['average_bitrate']/1000:.2f} kbps")
        print(f"Startup delay: {self.metrics['startup_delay']:.2f}s")
        print(f"Rebuffering events: {self.metrics['rebuffering_events']}")
        print(f"Total rebuffering time: {self.metrics['total_rebuffering_time']:.2f}s")
        print(f"Bitrate switches: {self.metrics['bitrate_switches']}")
        
        self.save_metrics(output_file)
        return True

    def generate_segment_url(self, base_url, segment_num):
        """Generate segment URL based on pattern"""
        if 'segment_' in base_url and '_.' in base_url:
            return base_url.replace('1_', f'{segment_num}_').replace('2_', f'{segment_num}_')
        elif '$Number$' in base_url:
            return base_url.replace('$Number$', str(segment_num))
        elif 'RepresentationID' in base_url:
            return base_url.replace('$Number$', str(segment_num))
        else:
            return f"{base_url}{segment_num}.m4s"

    def parse_mpd(self, content):
        """Parse MPD manifest"""
        try:
            root = ET.fromstring(content)
            ns = {'mpd': 'urn:mpeg:dash:schema:mpd:2011'}
            
            info = {
                'duration': root.get('mediaPresentationDuration'),
                'min_buffer_time': root.get('minBufferTime'),
                'type': root.get('type', 'static'),
                'periods': []
            }
            
            for period in root.findall('.//mpd:Period', ns):
                period_info = {
                    'id': period.get('id', '1'),
                    'adaptation_sets': []
                }
                
                for adapt_set in period.findall('.//mpd:AdaptationSet', ns):
                    adapt_info = {
                        'id': adapt_set.get('id', ''),
                        'content_type': adapt_set.get('contentType', ''),
                        'content_components': [],
                        'representations': []
                    }
                    
                    for comp in adapt_set.findall('.//mpd:ContentComponent', ns):
                        comp_info = {
                            'id': comp.get('id', ''),
                            'content_type': comp.get('contentType', '')
                        }
                        adapt_info['content_components'].append(comp_info)
                    
                    for rep in adapt_set.findall('.//mpd:Representation', ns):
                        rep_info = {
                            'id': rep.get('id', ''),
                            'bandwidth': int(rep.get('bandwidth', 0)) if rep.get('bandwidth') else 0,
                            'width': int(rep.get('width', 0)) if rep.get('width') else 0,
                            'height': int(rep.get('height', 0)) if rep.get('height') else 0,
                            'frame_rate': rep.get('frameRate', ''),
                            'codecs': rep.get('codecs', '')
                        }
                        
                        base_url_elem = rep.find('.//mpd:BaseURL', ns)
                        if base_url_elem is not None and base_url_elem.text:
                            rep_info['base_url'] = base_url_elem.text.strip()
                        else:
                            # Try adaptation set base URL
                            base_url_elem = adapt_set.find('.//mpd:BaseURL', ns)
                            if base_url_elem is not None and base_url_elem.text:
                                rep_info['base_url'] = base_url_elem.text.strip()
                            else:
                                rep_info['base_url'] = ''
                        
                        adapt_info['representations'].append(rep_info)
                    
                    period_info['adaptation_sets'].append(adapt_info)
                
                info['periods'].append(period_info)
            
            return info
        except Exception as e:
            print(f"Error parsing MPD: {e}")
            return None

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
    parser.add_argument('--duration', type=int, default=60, help='Download duration in seconds')
    parser.add_argument('--segment-length', type=int, default=4, choices=[2, 4, 6], help='Segment length in seconds')
    parser.add_argument('--abr', default='throughput', choices=['throughput', 'buffer', 'hybrid'], help='ABR algorithm')
    parser.add_argument('--buffer-target', type=int, default=15, help='Buffer target in seconds')
    
    args = parser.parse_args()
    
    downloader = DashVideoDownloader(args.manifest, args.abr, args.buffer_target)
    success = downloader.download_video(args.output, args.duration, args.segment_length)
    
    if not success:
        print("Download failed!")