import http.server
import socketserver
import json
import urllib.parse
import threading
import os
from database.db import get_connection

PORT = 8000
DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class PlanHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == '/api/plan':
            query = urllib.parse.parse_qs(parsed_path.query)
            patient_id = query.get('id', [None])[0]
            if patient_id:
                self._serve_json_data(patient_id)
            else:
                self.send_error(400, "Missing ID")
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/save':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            try:
                self._save_to_db(data)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            except Exception as e:
                self.send_error(500, str(e))

    def _serve_json_data(self, patient_id):
        conn = get_connection()
        # Get patient info
        patient = conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
        # Get latest plan
        plan = conn.execute("SELECT * FROM rehab_plans WHERE patient_id=? ORDER BY plan_date DESC LIMIT 1", (patient_id,)).fetchone()
        
        result = {
            "patient": dict(patient) if patient else {},
            "plan": dict(plan) if plan else {}
        }
        conn.close()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def _save_to_db(self, data):
        conn = get_connection()
        # Prepare columns and values
        # Removing 'id' from data if it exists to avoid衝突
        data.pop('id', None)
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        query = f"INSERT INTO rehab_plans ({cols}) VALUES ({placeholders})"
        conn.execute(query, list(data.values()))
        conn.commit()
        conn.close()

def start_server():
    try:
        handler = PlanHandler
        socketserver.TCPServer.allow_reuse_address = True
        httpd = socketserver.TCPServer(("", PORT), handler)
        print(f"Serving at port {PORT}")
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return httpd
    except Exception as e:
        print(f"Web Server failed to start: {e}")
        return None

if __name__ == "__main__":
    start_server()
    import time
    while True: time.sleep(1)
