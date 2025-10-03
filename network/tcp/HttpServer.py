#!/usr/bin/env python3
import http.server
import socketserver
import signal
import argparse
import sys
import time

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.server_name = kwargs.pop('server_name', 'unknown')
        self.verbose = kwargs.pop('verbose', False)
        super().__init__(*args, **kwargs)
        
    def log_message(self, format, *args):
        if self.verbose:
            super().log_message(format, *args)
    
    def do_GET(self):
        if self.verbose:
            print(f"(HttpServer) --> Received GET request from {self.client_address[0]} to path {self.path}")
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(f"Server: {self.server_name} - Path: {self.path}".encode())
        
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if self.verbose:
            print(f"(HttpServer) --> Received POST request from {self.client_address[0]} to path {self.path} with {content_length} bytes of data")
        post_data = self.rfile.read(content_length) if content_length > 0 else b''
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(f"Server: {self.server_name} - Received {len(post_data)} bytes".encode())

server = None
is_still_running = True

def handler_stop_signals(signum, frame):
    global is_still_running
    global server
    is_still_running = False
    if server:
        server.shutdown()
        print("> HTTP Server is shutdown gracefully")

def main():
    global server
    
    parser = argparse.ArgumentParser(description="HTTP Server",
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-n", "--server-name", help="Server's name like hs", required=True)
    parser.add_argument("-ip", "--server-ip", help="Server IP. E.g: 10.0.1.101", required=True)
    parser.add_argument("-v", "--verbose", action="store_true", help="Whether to log received messages information")
    
    config = vars(parser.parse_args())
    server_name = config['server_name']
    verbose = config['verbose']
    
    # Create a TCP server
    host = config['server_ip']  # Server IP
    port = 80                   # Port to listen on
    
    handler = lambda *args, **kwargs: CustomHTTPRequestHandler(*args, server_name=server_name, verbose=verbose, **kwargs)
    
    server = socketserver.TCPServer((host, port), handler)
    server.allow_reuse_address = True
    
    print(f"(HttpServer) --> Started server ({server_name}) at {time.strftime('%d/%m/%Y %H:%M:%S')}:")
    print(f"  - listening on ({host}:{port})")
    
    # Serve until interrupted
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("(HttpServer) <-- Server stopped")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, handler_stop_signals)
    signal.signal(signal.SIGTERM, handler_stop_signals)
    print("> HttpServer.__main__")
    
    retrys = 0
    max_retrys = 3
    already_up = False
    
    while (not already_up) and retrys < max_retrys and is_still_running:
        print(">> Try starting HTTP server")
        if retrys > 0:
            print(">>> Retry No. ", retrys)
        retrys += 1
        try:
            main()
            already_up = True
        except Exception as error:
            print("Error from HTTP server:", error)
            time.sleep(0.5)
    
    if (not already_up) and retrys >= max_retrys:
        print("Failed to start HTTP server after maximum attempts")