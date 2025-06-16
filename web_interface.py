import os
import sys
import importlib
from http.server import SimpleHTTPRequestHandler, HTTPServer
import json

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "plugins")

class PluginManager:
    def __init__(self, server):
        self.server = server
        self.plugins = []

    def load_plugins(self):
        sys.path.insert(0, PLUGINS_DIR)
        for fname in os.listdir(PLUGINS_DIR):
            if fname.endswith(".py") and not fname.startswith("_"):
                mod_name = fname[:-3]
                try:
                    mod = importlib.import_module(mod_name)
                    if hasattr(mod, "register"):
                        mod.register(self.server)
                        self.plugins.append(mod)
                        print(f"Loaded plugin: {mod_name}")
                except Exception as e:
                    print(f"Plugin load failed: {mod_name}: {e}")

class StageTwoHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.path = "/static/index.html"
        elif self.path.startswith("/static/"):
            self.path = self.path
        elif self.path == "/api/display":
            # Dummy display data (replace with real device logic)
            display = {
                "width": 240,
                "height": 135,
                "pixels": [0,0,0,255]*240*135  # RGBA black screen
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(display).encode())
            return
        elif self.path == "/api/plugins":
            plugins = [f[:-3] for f in os.listdir(PLUGINS_DIR) if f.endswith(".py") and not f.startswith("_")]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(plugins).encode())
            return
        else:
            # Let plugins handle custom routes
            for plugin in self.server.plugins:
                if hasattr(plugin, "handle_request"):
                    if plugin.handle_request(self):
                        return
        return super().do_GET()

def run_server(port=8080):
    os.chdir(os.path.dirname(__file__))
    handler = StageTwoHandler
    httpd = HTTPServer(("", port), handler)
    httpd.plugins = []
    plugin_manager = PluginManager(httpd)
    plugin_manager.load_plugins()
    httpd.plugins = plugin_manager.plugins
    print(f"StageTwo Web UI running at http://localhost:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()