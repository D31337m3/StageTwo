def register(server):
    # Optionally add attributes or methods to the server
    pass

def handle_request(handler):
    if handler.path == "/api/hello":
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(b'{"msg":"Hello from plugin!"}')
        return True
    return False