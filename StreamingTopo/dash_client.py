import requests
import xml.etree.ElementTree as ET
from urllib.request import urlopen
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
        self.manifest = self.parse_mpd(response.content)
        
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
        
        if not self.manifest or 'periods' not in self.manifest or not self.manifest['periods']:
            print("No manifest or periods found")
            return
        
        # Find video adaptation sets
        video_adaptations = []
        for period in self.manifest['periods']:
            for adapt_set in period['adaptation_sets']:
                # Check content type from content components or adaptation set
                content_type = adapt_set.get('content_type', '')
                content_types = [comp.get('content_type', '') for comp in adapt_set.get('content_components', [])]
                
                if 'video' in content_type.lower() or any('video' in ct.lower() for ct in content_types):
                    video_adaptations.append(adapt_set)
        
        print(f"Found {len(video_adaptations)} video adaptation sets")
        
        if not video_adaptations:
            print("No video adaptations found. Available adaptation sets:")
            for period in self.manifest['periods']:
                for i, adapt_set in enumerate(period['adaptation_sets']):
                    print(f"Period {period['id']}, Set {i}: Content types - {[comp.get('content_type', '') for comp in adapt_set.get('content_components', [])]}")
            return
        
        # Select the best quality representation (highest bandwidth)
        best_representation = None
        for adapt_set in video_adaptations:
            for rep in adapt_set.get('representations', []):
                if (best_representation is None or 
                    rep.get('bandwidth', 0) > best_representation.get('bandwidth', 0)):
                    best_representation = rep
        
        if not best_representation:
            print("No video representations found")
            return
        
        print(f"Selected representation: {best_representation['id']} "
            f"({best_representation['bandwidth']} bps, "
            f"{best_representation.get('width', 'N/A')}x{best_representation.get('height', 'N/A')})")
        
        # Now proceed with downloading segments
        base_url = best_representation.get('base_url')
        if not base_url:
            print("No base URL found in representation")
            return
    
        # Make URL absolute if it's relative
        if not base_url.startswith(('http://', 'https://')):
            # Extract base path from manifest URL
            if hasattr(self, 'manifest_url'):
                base_dir = '/'.join(self.manifest_url.split('/')[:-1]) + '/'
                base_url = base_dir + base_url
            else:
                print("Cannot resolve relative URL without manifest_url")
                return False
    
        print(f"Base URL: {base_url}")
    
        # Download the video
        return self.download_segments(base_url, output_file, best_representation, duration)

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

    def download_segments(self, base_url, output_file, representation, duration=60):
        """Download video segments and concatenate them"""
        # For static MPD with SegmentBase, we might have a single file
        # or need to handle initialization + media segments
        
        # Check if we have initialization data
        init_range = None
        if 'initialization' in representation:
            init_range = representation['initialization'].get('range')
        
        # For simple MPD with single file segments
        if base_url.endswith('.mp4') or base_url.endswith('.m4s'):
            # Single file download
            print(f"Downloading single file: {base_url}")
            response = requests.get(base_url, stream=True)
            response.raise_for_status()
            
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"Download completed: {output_file}")
            return True
        
        else:
            # Handle multiple segments (more complex DASH)
            # This is a simplified approach - real DASH would need segment template parsing
            print("Multi-segment DASH detected - using simplified download")
            
            # Try to download the first few segments
            segment_files = []
            
            # Download initialization segment if available
            if init_range:
                print(f"Downloading initialization segment: {init_range}")
                # This would need proper byte range handling
                pass
            
            # Download media segments
            segment_pattern = self.detect_segment_pattern(base_url)
            
            for i in range(1, 10):  # Download first 10 segments as example
                segment_url = segment_pattern.format(i)
                segment_file = f"segment_{i}.tmp"
                
                print(f"Downloading segment {i}: {segment_url}")
                response = requests.get(segment_url, stream=True)
                response.raise_for_status()
                
                with open(segment_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                segment_files.append(segment_file)
            
            # Concatenate segments
            self.concatenate_segments(segment_files, output_file)
            
            # Clean up temporary files
            for seg_file in segment_files:
                os.remove(seg_file)
            
            print(f"Download completed: {output_file}")
            return True

    def detect_segment_pattern(self, base_url):
        """Detect segment URL pattern"""
        # Simple pattern detection - in real DASH this would parse SegmentTemplate
        if 'segment_' in base_url and '_.' in base_url:
            # Pattern like "segment_1_.mp4", "segment_2_.mp4"
            return base_url.replace('1_', '{}_').replace('2_', '{}_')
        else:
            # Default pattern guessing
            return base_url.replace('.mp4', '{}.mp4').replace('.m4s', '{}.m4s')

    def concatenate_segments(self, segment_files, output_file):
        """Concatenate video segments into single file"""
        try:
            with open(output_file, 'wb') as outfile:
                for segment_file in segment_files:
                    with open(segment_file, 'rb') as infile:
                        outfile.write(infile.read())
            return True
        except Exception as e:
            print(f"Error concatenating segments: {e}")
            return False

# Usage example
if __name__ == "__main__":
    manifest_url = "http://10.0.0.2:8080/manifest.mpd"
    downloader = DashVideoDownloader(manifest_url)
    downloader.download_video("dash_output.mp4", duration=30)  # Download 30 seconds of video