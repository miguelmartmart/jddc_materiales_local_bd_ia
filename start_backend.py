"""
start_backend.py — Inicia el backend con --timeout-keep-alive 620 y verifica /ping
"""
import subprocess
import sys
import time
import urllib.request
import os

DIR = os.path.dirname(os.path.abspath(__file__))

# Kill any existing backend on port 8001
import socket
def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if port_in_use(8001):
    print("Port 8001 in use — killing existing process...")
    # Find and kill
    import subprocess as sp
    result = sp.run(['netstat', '-ano'], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if ':8001' in line and 'LISTENING' in line:
            pid = line.strip().split()[-1]
            print(f"  Killing PID {pid}")
            sp.run(['taskkill', '/F', '/PID', pid], capture_output=True)
    time.sleep(2)

# Start backend
env = os.environ.copy()
env['PYTHONPATH'] = DIR

print("Starting backend with --timeout-keep-alive 620...")
proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'backend.main:app',
     '--host', '0.0.0.0', '--port', '8001',
     '--log-level', 'warning',
     '--timeout-keep-alive', '620'],
    cwd=DIR,
    env=env,
    stdout=open(os.path.join(DIR, 'backend_log5.txt'), 'w'),
    stderr=open(os.path.join(DIR, 'backend_err5.txt'), 'w'),
)
print(f"PID={proc.pid}")

# Wait for startup
for i in range(15):
    time.sleep(1)
    if port_in_use(8001):
        print(f"Backend up after {i+1}s")
        break
    print(f"  Waiting... {i+1}s")
else:
    print("ERROR: Backend did not start in 15s")
    # Show errors
    with open(os.path.join(DIR, 'backend_err5.txt')) as f:
        print(f.read()[-2000:])
    sys.exit(1)

# Test /health
try:
    r = urllib.request.urlopen('http://localhost:8001/health', timeout=5)
    print(f"Health: {r.status} OK")
except Exception as e:
    print(f"Health FAIL: {e}")

# Test /api/chat/ping
try:
    r = urllib.request.urlopen('http://localhost:8001/api/chat/ping', timeout=5)
    print(f"Ping: {r.status} {r.read().decode()}")
except Exception as e:
    print(f"Ping FAIL: {e}")
    # Show last errors
    with open(os.path.join(DIR, 'backend_err5.txt')) as f:
        content = f.read()
    print("Last 20 lines of backend_err5.txt:")
    print('\n'.join(content.splitlines()[-20:]))
