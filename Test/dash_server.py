from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import argparse

class CORSHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

def create_sample_dash_content(directory):
    """Create sample DASH content if it doesn't exist"""
    os.makedirs(directory, exist_ok=True)
    
    # Create sample manifest
    manifest_content = '''<?xml version="1.0" encoding="UTF-8"?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" mediaPresentationDuration="PT60S">
  <Period id="1">
    <AdaptationSet contentType="video" segmentAlignment="true">
      <Representation id="1" bandwidth="400000" codecs="avc1.42c00d" width="426" height="240">
        <BaseURL>segment_$Number$.m4s</BaseURL>
        <SegmentBase indexRange="0-100">
          <Initialization range="0-100"/>
        </SegmentBase>
      </Representation>
      <Representation id="2" bandwidth="800000" codecs="avc1.42c00d" width="640" height="360">
        <BaseURL>segment_$Number$.m4s</BaseURL>
        <SegmentBase indexRange="0-100">
          <Initialization range="0-100"/>
        </SegmentBase>
      </Representation>
    </AdaptationSet>
  </Period>
</MPD>'''
    
    manifest_path = os.path.join(directory, 'manifest.mpd')
    if not os.path.exists(manifest_path):
        with open(manifest_path, 'w') as f:
            f.write(manifest_content)
        print(f"Created sample manifest: {manifest_path}")
    
    # Create sample segments
    for i in range(1, 16):  # 15 segments
        segment_path = os.path.join(directory, f'segment_{i}.m4s')
        if not os.path.exists(segment_path):
            # Create a small dummy segment (100KB)
            with open(segment_path, 'wb') as f:
                f.write(b'0' * 102400)  # 100KB
            print(f"Created sample segment: {segment_path}")

def run_server(host='10.0.0.2', port=8080, directory='dash_content'):
    # Create sample content
    create_sample_dash_content(directory)
    
    # Change to directory
    original_dir = os.getcwd()
    os.chdir(directory)
    
    try:
        server_address = (host, port)
        httpd = HTTPServer(server_address, CORSHTTPRequestHandler)
        print(f'✓ DASH Server running on {host}:{port}')
        print(f'Serving from: {os.path.abspath(".")}')
        print('Available files:')
        for file in os.listdir('.'):
            print(f'  {file}')
        httpd.serve_forever()
    except Exception as e:
        print(f'Failed to start DASH server: {e}')
    finally:
        os.chdir(original_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='10.0.0.2', help='Server host')
    parser.add_argument('--port', type=int, default=8080, help='Server port')
    parser.add_argument('--dir', default='dash_content', help='Content directory')
    
    args = parser.parse_args()
    
    print("Starting DASH HTTP Server...")
    run_server(args.host, args.port, args.dir)