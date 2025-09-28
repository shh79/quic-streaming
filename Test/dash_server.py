from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import argparse

class CORSHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def run_server(host='10.0.0.2', port=8080, directory='dash_content'):
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")
        print("Please place your DASH content (manifest.mpd and video segments) in this directory")
    
    os.chdir(directory)
    server_address = (host, port)
    httpd = HTTPServer(server_address, CORSHTTPRequestHandler)
    print(f'Serving DASH content from {directory} on {host}:{port}')
    httpd.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='10.0.0.2', help='Server host')
    parser.add_argument('--port', type=int, default=8080, help='Server port')
    parser.add_argument('--dir', default='dash_content', help='Content directory')
    
    args = parser.parse_args()
    run_server(args.host, args.port, args.dir)