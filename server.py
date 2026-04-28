from flask import Flask, jsonify, send_from_directory
import requests
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

app = Flask(__name__, static_folder='public')

SERVICES = [
    {"id": "dashboard",     "port": 80},
    {"id": "analist",       "port": 5000},
    {"id": "subyoutube",    "port": 5001},
    {"id": "consiliu",      "port": 5555},
    {"id": "xtts",          "port": 8001},
    {"id": "translate",     "port": 8002},
    {"id": "tts_ro",        "port": 8003},
    {"id": "ocr",           "port": 8004},
    {"id": "ocr_paddle",    "port": 8005},
    {"id": "summarizer",    "port": 8007},
    {"id": "extractor",     "port": 8008},
    {"id": "transcriber",   "port": 8009},
    {"id": "biblioteca",    "port": 8015},
    {"id": "face",          "port": 8020},
    {"id": "ora_biz",       "port": 7700},
    {"id": "optica",        "port": 7800},
    {"id": "genetica",      "port": 8780},
    {"id": "factcheck",     "port": 8765},
    {"id": "linkrag",       "port": 8770},
    {"id": "contabilitate", "port": 8790},
    {"id": "doctor",        "port": 8800},
    {"id": "sysmon",        "port": 9090},
    {"id": "sdr_tracker",  "port": 8810},
]

def check_service(svc):
    try:
        r = requests.get(f"http://localhost:{svc['port']}/", timeout=2)
        return {"id": svc["id"], "up": r.status_code < 500}
    except Exception:
        return {"id": svc["id"], "up": False}

SYSTEMD_SERVICES = [
    'ppaisie.service',
    'ora-bizantina.service',
    'laborator-optica.service',
    'laborator-genetica.service',
    'sdr_tracker.service',
    'factcheck.service',
    'linkrag.service',
    'contabilitate-legi.service',
    'doctor-ai.service',
    'sysmon.service',
]

def start_one(svc):
    r = subprocess.run(['sudo', 'systemctl', 'start', svc], capture_output=True, text=True)
    return svc, r.returncode == 0

@app.route('/api/start-all', methods=['POST'])
def start_all():
    results = {}
    with ThreadPoolExecutor(max_workers=len(SYSTEMD_SERVICES)) as ex:
        futures = {ex.submit(start_one, s): s for s in SYSTEMD_SERVICES}
        for f in as_completed(futures):
            name, ok = f.result()
            results[name] = ok
    return jsonify({'ok': True, 'results': results})

@app.route('/api/status')
def status():
    results = {}
    with ThreadPoolExecutor(max_workers=len(SERVICES)) as ex:
        futures = {ex.submit(check_service, s): s for s in SERVICES}
        for f in as_completed(futures):
            r = f.result()
            results[r["id"]] = r["up"]
    return jsonify(results)

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=False)
