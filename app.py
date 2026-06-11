import http.server
import socket


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"Hello from {socket.gethostname()}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # geen access-log nodig voor het lab


http.server.ThreadingHTTPServer(("", 8000), Handler).serve_forever()
