#dash_server.py
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

def run_server(port=8080, directory='./dash_content'):
    os.chdir(directory)
    server_address = ('10.0.0.2', port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print(f'Serving DASH content on port {port}')
    httpd.serve_forever()

run_server()