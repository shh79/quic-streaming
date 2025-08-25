import requests
import xml.etree.ElementTree as ET
import time
import os

class DashVideoDownloader:
    def __init__(self, manifest_url):
        self.manifest_url = manifest_url
        self.manifest = None
        self.current_quality = 0
        self.download_history = []
        
    def fetch_manifest(self):
        """Download and parse the DASH manifest"""
        response = requests.get(self.manifest_url)
        self.manifest = self.parse_mpd(response.content)
        
    def get_available_bitrates(self):
        """Return available bitrates sorted from lowest to highest"""
        if not self.manifest:
            self.fetch_manifest()
            
        # Extract video representations from the dictionary structure
        video_reps = []
        for period in self.manifest['periods']:
            for adapt_set in period['adaptation_sets']:
                content_types = [comp.get('content_type', '') 
                               for comp in adapt_set.get('content_components', [])]
                if any('video' in ct.lower() for ct in content_types):
                    for rep in adapt_set.get('representations', []):
                        video_reps.append((rep.get('bandwidth', 0), rep.get('id', ''), rep))
        
        # Sort by bandwidth
        return sorted(video_reps, key=lambda x: x[0])
    
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
    
    def select_quality_index(self):
        """Select appropriate quality index based on network conditions"""
        available_qualities = self.get_available_bitrates()
        if not available_qualities:
            return 0
            
        condition = self.get_network_condition()
        
        if condition == "poor":
            return 0  # lowest quality
        elif condition == "moderate":
            return len(available_qualities) // 2  # middle quality
        else:
            return len(available_qualities) - 1  # highest quality
    
    def get_representation_by_index(self, quality_index):
        """Get representation by quality index"""
        available_qualities = self.get_available_bitrates()
        if 0 <= quality_index < len(available_qualities):
            return available_qualities[quality_index][2]  # Return the rep dict
        return available_qualities[-1][2] if available_qualities else None

    def download_segment(self, segment_url):
        """Download a single segment and measure performance"""
        start_time = time.time()
        response = requests.get(segment_url, stream=True)
        response.raise_for_status()
        
        # Read the content to measure download
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
        
        download_time = time.time() - start_time
        segment_size = len(content)
        bitrate = self.calculate_current_bitrate(segment_size, download_time)
        
        # Store this download's metrics
        self.download_history.append((bitrate, download_time))
        
        return content

    def download_video(self, output_file, duration=60):
        """Download video segments with adaptive quality"""
        if not self.manifest:
            self.fetch_manifest()
        
        if not self.manifest or 'periods' not in self.manifest or not self.manifest['periods']:
            print("No manifest or periods found")
            return False
        
        # Get all available qualities
        available_qualities = self.get_available_bitrates()
        if not available_qualities:
            print("No video representations found")
            return False
        
        print(f"Available qualities: {[(q[0], q[1]) for q in available_qualities]}")
        
        # Start with middle quality
        current_quality_index = len(available_qualities) // 2
        segment_count = 0
        total_downloaded = 0
        
        with open(output_file, 'wb') as output_f:
            # Download segments with adaptive quality
            for segment_num in range(1, 100):  # Limit to 100 segments for safety
                # Select quality based on current network conditions
                current_quality_index = self.select_quality_index()
                representation = self.get_representation_by_index(current_quality_index)
                
                if not representation:
                    print("No representation found for selected quality")
                    break
                
                base_url = representation.get('base_url', '')
                if not base_url:
                    print("No base URL found")
                    break
                
                # Make URL absolute if relative
                if not base_url.startswith(('http://', 'https://')):
                    base_dir = '/'.join(self.manifest_url.split('/')[:-1]) + '/'
                    base_url = base_dir + base_url
                
                # Generate segment URL
                segment_url = self.generate_segment_url(base_url, segment_num)
                
                print(f"Downloading segment {segment_num} at quality {current_quality_index} "
                      f"({representation.get('bandwidth', 0)} bps)")
                
                try:
                    # Download segment and measure performance
                    segment_data = self.download_segment(segment_url)
                    output_f.write(segment_data)
                    
                    segment_count += 1
                    total_downloaded += len(segment_data)
                    
                    # Print network status
                    if self.download_history:
                        recent_bitrate = self.download_history[-1][0]
                        print(f"  Network: {recent_bitrate/1000000:.2f} Mbps, "
                              f"Condition: {self.get_network_condition()}")
                    
                    # Check if we've reached the desired duration
                    if total_downloaded > duration * 1024 * 1024:  # Approximate based on MB
                        break
                        
                except requests.RequestException as e:
                    print(f"Error downloading segment {segment_num}: {e}")
                    # Lower quality on error
                    current_quality_index = max(0, current_quality_index - 1)
                    time.sleep(1)  # Wait before retry
                    continue
        
        print(f"Download completed: {segment_count} segments, {total_downloaded/1024/1024:.2f} MB")
        return True

    def generate_segment_url(self, base_url, segment_num):
        """Generate segment URL based on pattern"""
        if 'segment_' in base_url and '_.' in base_url:
            # Pattern like "segment_1_.mp4" -> "segment_X_.mp4"
            return base_url.replace('1_', f'{segment_num}_').replace('2_', f'{segment_num}_')
        elif '$Number$' in base_url:
            # Template pattern
            return base_url.replace('$Number$', str(segment_num))
        else:
            # Default: append segment number
            return f"{base_url}.{segment_num}"

    def parse_mpd(self, content):
        """Parse MPD manifest using built-in XML parser"""
        
        # Parse XML
        root = ET.fromstring(content)
        
        # Define namespace (MPD uses namespaces)
        ns = {'mpd': 'urn:mpeg:dash:schema:mpd:2011'}
        
        # Extract basic info
        info = {
            'duration': root.get('mediaPresentationDuration'),
            'min_buffer_time': root.get('minBufferTime'),
            'type': root.get('type', 'static'),
            'profiles': root.get('profiles', ''),
            'periods': []
        }
        
        # Parse periods
        for period in root.findall('.//mpd:Period', ns):
            period_info = {
                'id': period.get('id', '1'),  # default id if not present
                'start': period.get('start', ''),
                'duration': period.get('duration', ''),
                'adaptation_sets': []
            }
            
            # Parse adaptation sets
            for adapt_set in period.findall('.//mpd:AdaptationSet', ns):
                adapt_info = {
                    'id': adapt_set.get('id', ''),
                    'segment_alignment': adapt_set.get('segmentAlignment', ''),
                    'max_width': adapt_set.get('maxWidth', ''),
                    'max_height': adapt_set.get('maxHeight', ''),
                    'max_frame_rate': adapt_set.get('maxFrameRate', ''),
                    'par': adapt_set.get('par', ''),
                    'lang': adapt_set.get('lang', ''),
                    'content_components': [],  # Store content components separately
                    'representations': []
                }
                
                # Parse content components to determine content type
                for comp in adapt_set.findall('.//mpd:ContentComponent', ns):
                    comp_info = {
                        'id': comp.get('id', ''),
                        'content_type': comp.get('contentType', '')
                    }
                    adapt_info['content_components'].append(comp_info)
                
                # Determine main content type from components
                content_types = [comp.get('contentType', '') for comp in adapt_set.findall('.//mpd:ContentComponent', ns)]
                if content_types:
                    adapt_info['content_type'] = content_types[0]  # Use first content type
                else:
                    adapt_info['content_type'] = ''  # Fallback
                
                # Parse representations
                for rep in adapt_set.findall('.//mpd:Representation', ns):
                    rep_info = {
                        'id': rep.get('id', ''),
                        'mime_type': rep.get('mimeType', ''),
                        'codecs': rep.get('codecs', ''),
                        'bandwidth': int(rep.get('bandwidth', 0)) if rep.get('bandwidth') else 0,
                        'width': int(rep.get('width', 0)) if rep.get('width') else 0,
                        'height': int(rep.get('height', 0)) if rep.get('height') else 0,
                        'frame_rate': rep.get('frameRate', ''),
                        'sar': rep.get('sar', '')
                    }
                    
                    # Get base URL
                    base_url_elem = rep.find('.//mpd:BaseURL', ns)
                    if base_url_elem is not None and base_url_elem.text:
                        rep_info['base_url'] = base_url_elem.text.strip()
                    else:
                        rep_info['base_url'] = ''
                    
                    # Get segment base info
                    segment_base = rep.find('.//mpd:SegmentBase', ns)
                    if segment_base is not None:
                        rep_info['segment_base'] = {
                            'index_range': segment_base.get('indexRange', ''),
                            'index_range_exact': segment_base.get('indexRangeExact', '')
                        }
                        
                        # Get initialization info
                        initialization = segment_base.find('.//mpd:Initialization', ns)
                        if initialization is not None:
                            rep_info['initialization'] = {
                                'range': initialization.get('range', '')
                            }
                    
                    adapt_info['representations'].append(rep_info)
                
                period_info['adaptation_sets'].append(adapt_info)
            
            info['periods'].append(period_info)
        
        return info
    
# Usage example
if __name__ == "__main__":
    manifest_url = "http://10.0.0.2:8080/manifest.mpd"
    downloader = DashVideoDownloader(manifest_url)
    downloader.download_video("dash_output.mp4", duration=30)  # Download 30 seconds of video