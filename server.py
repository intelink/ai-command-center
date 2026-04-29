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
    {"id": "sdr_tracker",       "port": 8810},
    {"id": "intelligence_graph","port": 8820},
    {"id": "ocr_bizantine",     "port": 8830},
    {"id": "kraken_gr",         "port": 8840},
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
    'ocr-bizantine.service',
    'kraken-gr.service',
]

def start_one(svc):
    r = subprocess.run(['sudo', 'systemctl', 'start', svc], capture_output=True, text=True)
    return svc, r.returncode == 0

def stop_one(svc):
    r = subprocess.run(['sudo', 'systemctl', 'stop', svc], capture_output=True, text=True)
    return svc, r.returncode == 0

def get_gpu_info():
    try:
        out = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=name,memory.used,memory.total,utilization.gpu',
             '--format=csv,noheader,nounits'],
            text=True, timeout=3
        ).strip()
        parts = [p.strip() for p in out.split(',')]
        return {
            'name': parts[0],
            'used_mb': int(parts[1]),
            'total_mb': int(parts[2]),
            'util_pct': int(parts[3]),
        }
    except Exception:
        return None

@app.route('/api/start-all', methods=['POST'])
def start_all():
    results = {}
    with ThreadPoolExecutor(max_workers=len(SYSTEMD_SERVICES)) as ex:
        futures = {ex.submit(start_one, s): s for s in SYSTEMD_SERVICES}
        for f in as_completed(futures):
            name, ok = f.result()
            results[name] = ok
    return jsonify({'ok': True, 'results': results})

@app.route('/api/stop-all', methods=['POST'])
def stop_all():
    results = {}
    with ThreadPoolExecutor(max_workers=len(SYSTEMD_SERVICES)) as ex:
        futures = {ex.submit(stop_one, s): s for s in SYSTEMD_SERVICES}
        for f in as_completed(futures):
            name, ok = f.result()
            results[name] = ok
    return jsonify({'ok': True, 'results': results})

@app.route('/api/restart-all', methods=['POST'])
def restart_all():
    # Stop first (sequential — frees GPU memory before restart)
    with ThreadPoolExecutor(max_workers=len(SYSTEMD_SERVICES)) as ex:
        list(ex.map(stop_one, SYSTEMD_SERVICES))
    # Then start all in parallel
    results = {}
    with ThreadPoolExecutor(max_workers=len(SYSTEMD_SERVICES)) as ex:
        futures = {ex.submit(start_one, s): s for s in SYSTEMD_SERVICES}
        for f in as_completed(futures):
            name, ok = f.result()
            results[name] = ok
    return jsonify({'ok': True, 'results': results})

@app.route('/api/gpu')
def gpu_status():
    return jsonify(get_gpu_info() or {})

@app.route('/api/free-gpu', methods=['POST'])
def free_gpu():
    """Kill all processes currently using GPU VRAM (except pid 1 and kernel)."""
    try:
        out = subprocess.check_output(
            ['nvidia-smi', '--query-compute-apps=pid,used_memory,name',
             '--format=csv,noheader,nounits'],
            text=True, timeout=5
        ).strip()
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

    killed = []
    errors = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(',')]
        pid = int(parts[0])
        mem_mb = int(parts[1]) if len(parts) > 1 else 0
        name = parts[2] if len(parts) > 2 else ''
        if pid <= 1:
            continue
        try:
            subprocess.run(['sudo', 'kill', '-9', str(pid)], check=True)
            killed.append({'pid': pid, 'mem_mb': mem_mb, 'name': name})
            logging.info(f"Killed GPU process pid={pid} mem={mem_mb}MB name={name}")
        except Exception as e:
            errors.append({'pid': pid, 'error': str(e)})

    freed_mb = sum(p['mem_mb'] for p in killed)

    # Sync systemd state: stop all services so "start-all" works correctly afterward.
    # Without this, systemd sees them as "active" (nohup orphans) and skips start.
    if killed:
        with ThreadPoolExecutor(max_workers=len(SYSTEMD_SERVICES)) as ex:
            list(ex.map(stop_one, SYSTEMD_SERVICES))

    return jsonify({'ok': True, 'killed': killed, 'freed_mb': freed_mb, 'errors': errors})

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
