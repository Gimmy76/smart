# Add this to network/tcp/SimpleHttpServer.py
import http.server
import socketserver
import threading
import signal
import sys
import time

PORT = 80
RUNNING = True

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging for cleaner output
        pass
        
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Hello, World!')
        
    def do_POST(self):
        content_length = int(self.headers['Content-Length']) if 'Content-Length' in self.headers else 0
        post_data = self.rfile.read(content_length)
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Received POST data')

def signal_handler(sig, frame):
    global RUNNING
    RUNNING = False
    sys.exit(0)

def run_server(server_ip):
    server = socketserver.TCPServer((server_ip, PORT), Handler)
    server.allow_reuse_address = True
    
    print(f"Starting HTTP Server on {server_ip}:{PORT}")
    try:
        while RUNNING:
            server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("HTTP Server stopped")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 SimpleHttpServer.py <server_ip>")
        sys.exit(1)
        
    server_ip = sys.argv[1]
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    server_thread = threading.Thread(target=run_server, args=(server_ip,))
    server_thread.daemon = True
    server_thread.start()
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")