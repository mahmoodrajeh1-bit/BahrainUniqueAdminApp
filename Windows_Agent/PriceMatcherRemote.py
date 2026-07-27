
import json
import secrets
import socket
import sys
import threading
import tkinter as tk
import urllib.parse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PriceMatcher import PriceMatcherApp


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = app_dir()
CONFIG_FILE = BASE_DIR / "remote_config.json"
DEFAULT_PORT = 8765
MOBILE_HTML = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n<meta name="theme-color" content="#111827">\n<title>PriceMatcher Remote</title>\n<style>\n:root{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#111827;background:#f3f4f6}\n*{box-sizing:border-box} body{margin:0;padding:16px;max-width:920px;margin:auto}\nheader{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}\nh1{font-size:22px;margin:0}.small{font-size:12px;color:#6b7280}\n.card{background:white;border-radius:16px;padding:16px;margin:12px 0;box-shadow:0 2px 12px #00000012}\n.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}\n.stat{background:#f9fafb;border-radius:12px;padding:12px}.stat b{font-size:20px;display:block}\n.online{color:#059669}.offline{color:#dc2626}\nbutton{border:0;border-radius:12px;padding:13px 16px;font-weight:700;font-size:15px;cursor:pointer}\n.primary{background:#2563eb;color:white}.warn{background:#f59e0b;color:white}\n.danger{background:#dc2626;color:white}.neutral{background:#e5e7eb;color:#111827}\n.controls{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}\ninput{width:100%;padding:12px;border:1px solid #d1d5db;border-radius:10px;font-size:15px;margin:5px 0 10px}\n.bot{border:2px solid transparent}.bot.selected{border-color:#2563eb}\n.row{display:flex;gap:8px;align-items:center}.row>*{flex:1}\npre{white-space:pre-wrap;word-break:break-word;background:#111827;color:#e5e7eb;padding:12px;border-radius:10px;max-height:220px;overflow:auto;font-size:11px}\n.hidden{display:none}.pill{padding:5px 9px;border-radius:999px;background:#e5e7eb;font-size:12px}\n</style>\n</head>\n<body>\n<header>\n<div><h1>PriceMatcher Remote</h1><div class="small">Control registered laptops through Tailscale</div></div>\n<button class="neutral" onclick="showAdd()">+ Laptop</button>\n</header>\n\n<div id="addCard" class="card hidden">\n<h3>Add or edit laptop</h3>\n<label>Display name</label><input id="name" placeholder="Office Laptop">\n<label>Address</label><input id="url" placeholder="http://100.x.x.x:8765">\n<label>Access token</label><input id="token" placeholder="Token from the Windows app">\n<div class="row"><button class="primary" onclick="saveBot()">Save</button><button class="neutral" onclick="hideAdd()">Cancel</button></div>\n</div>\n\n<div id="bots"></div>\n\n<div id="panel" class="hidden">\n<div class="card">\n<div class="row"><div><h2 id="selectedName" style="margin:0"></h2><div id="connection" class="small">Checking…</div></div><span id="statePill" class="pill">Unknown</span></div>\n</div>\n\n<div class="card">\n<div class="grid">\n<div class="stat"><span class="small">Cycle</span><b id="cycle">0</b></div>\n<div class="stat"><span class="small">Page</span><b id="page">0</b></div>\n<div class="stat"><span class="small">Checked</span><b id="checked">0</b></div>\n<div class="stat"><span class="small">Updated</span><b id="updated">0</b></div>\n<div class="stat"><span class="small">Skipped</span><b id="skipped">0</b></div>\n<div class="stat"><span class="small">Errors</span><b id="errors">0</b></div>\n</div>\n</div>\n\n<div class="card controls">\n<button class="primary" onclick="commandBot(\'start\')">Start</button>\n<button class="warn" onclick="commandBot(\'pause\')">Pause</button>\n<button class="primary" onclick="commandBot(\'resume\')">Resume</button>\n<button class="danger" onclick="commandBot(\'stop\')">Stop</button>\n</div>\n\n<div class="card"><h3>Recent activity</h3><pre id="logs">No logs yet.</pre></div>\n</div>\n\n<script>\nlet bots=JSON.parse(localStorage.getItem(\'pm_bots\')||\'[]\');\nlet selected=localStorage.getItem(\'pm_selected\')||\'\';\nlet timer=null, editingIndex=-1;\n\nfunction esc(s){return String(s).replace(/[&<>"\']/g,m=>({\'&\':\'&amp;\',\'<\':\'&lt;\',\'>\':\'&gt;\',\'"\':\'&quot;\',"\'":\'&#39;\'}[m]))}\nfunction renderBots(){\n const el=document.getElementById(\'bots\');\n if(!bots.length){\n  el.innerHTML=\'<div class="card"><b>No laptops registered.</b><div class="small">Tap “+ Laptop” and enter the Tailscale address and token shown on the Windows app.</div></div>\';\n  document.getElementById(\'panel\').classList.add(\'hidden\'); return;\n }\n el.innerHTML=bots.map((b,i)=>`<div class="card bot ${selected===b.id?\'selected\':\'\'}" onclick="selectBot(\'${b.id}\')">\n <div class="row"><div><b>${esc(b.name)}</b><div class="small">${esc(b.url)}</div></div>\n <button class="neutral" onclick="event.stopPropagation();editBot(${i})">Edit</button>\n <button class="danger" onclick="event.stopPropagation();removeBot(${i})">Remove</button></div></div>`).join(\'\');\n if(!selected) selectBot(bots[0].id); else refresh();\n}\nfunction showAdd(){editingIndex=-1;document.getElementById(\'name\').value=\'\';document.getElementById(\'url\').value=\'http://\';document.getElementById(\'token\').value=\'\';document.getElementById(\'addCard\').classList.remove(\'hidden\')}\nfunction hideAdd(){document.getElementById(\'addCard\').classList.add(\'hidden\')}\nfunction editBot(i){editingIndex=i;let b=bots[i];document.getElementById(\'name\').value=b.name;document.getElementById(\'url\').value=b.url;document.getElementById(\'token\').value=b.token;document.getElementById(\'addCard\').classList.remove(\'hidden\')}\nfunction saveBot(){\n let n=document.getElementById(\'name\').value.trim();\n let u=document.getElementById(\'url\').value.trim().replace(/\\/$/,\'\');\n let t=document.getElementById(\'token\').value.trim();\n if(!n||!u||!t){alert(\'Please complete all fields.\');return}\n let b={id: editingIndex>=0?bots[editingIndex].id:(Date.now().toString(36)+Math.random().toString(36).slice(2)),name:n,url:u,token:t};\n if(editingIndex>=0) bots[editingIndex]=b; else bots.push(b);\n localStorage.setItem(\'pm_bots\',JSON.stringify(bots));hideAdd();selectBot(b.id);\n}\nfunction removeBot(i){\n if(!confirm(\'Remove this laptop?\'))return;\n let id=bots[i].id;bots.splice(i,1);if(selected===id)selected=\'\';\n localStorage.setItem(\'pm_bots\',JSON.stringify(bots));localStorage.setItem(\'pm_selected\',selected);renderBots();\n}\nfunction selectBot(id){\n selected=id;localStorage.setItem(\'pm_selected\',id);\n document.getElementById(\'panel\').classList.remove(\'hidden\');\n renderBotsOnly();refresh();\n if(timer)clearInterval(timer);timer=setInterval(refresh,3000);\n}\nfunction renderBotsOnly(){document.querySelectorAll(\'.bot\').forEach((x,i)=>x.classList.toggle(\'selected\',bots[i].id===selected))}\nfunction current(){return bots.find(b=>b.id===selected)}\nasync function api(path,opts={}){\n let b=current();if(!b)throw new Error(\'No laptop selected\');\n opts.headers=Object.assign({\'Authorization\':\'Bearer \'+b.token,\'Content-Type\':\'application/json\'},opts.headers||{});\n let r=await fetch(b.url+path,opts);\n if(!r.ok)throw new Error((await r.text())||(\'HTTP \'+r.status));\n return r.json();\n}\nasync function refresh(){\n let b=current();if(!b)return;\n document.getElementById(\'selectedName\').textContent=b.name;\n try{\n  let s=await api(\'/api/status\');\n  let c=document.getElementById(\'connection\');\n  c.textContent=\'Online • \'+s.computer_name+\' • \'+s.address;c.className=\'small online\';\n  document.getElementById(\'statePill\').textContent=s.state;\n  [\'cycle\',\'page\',\'checked\',\'updated\',\'skipped\',\'errors\'].forEach(k=>document.getElementById(k).textContent=s.stats[k]??0);\n  document.getElementById(\'logs\').textContent=(s.logs||[]).join(\'\')||\'No logs yet.\';\n }catch(e){\n  let c=document.getElementById(\'connection\');\n  c.textContent=\'Offline or unreachable: \'+e.message;c.className=\'small offline\';\n  document.getElementById(\'statePill\').textContent=\'Offline\';\n }\n}\nasync function commandBot(cmd){\n try{await api(\'/api/\'+cmd,{method:\'POST\',body:\'{}\'});setTimeout(refresh,500)}\n catch(e){alert(e.message)}\n}\nrenderBots();\n</script>\n</body></html>'


def load_config():
    cfg = {
        "computer_name": socket.gethostname() or "PriceMatcher PC",
        "port": DEFAULT_PORT,
        "token": secrets.token_urlsafe(24),
    }
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            for key in cfg:
                if key in saved:
                    cfg[key] = saved[key]
        except Exception:
            pass
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


CONFIG = load_config()
APP = None


class RemotePriceMatcherApp(PriceMatcherApp):
    def __init__(self, root):
        super().__init__(root)
        self.remote_logs = deque(maxlen=200)

        remote_frame = tk.LabelFrame(root, text="Phone Remote Access", padx=10, pady=8)
        remote_frame.pack(fill=tk.X, padx=12, pady=(0, 8), before=self.log_box)

        self.remote_info_var = tk.StringVar()
        tk.Label(remote_frame, textvariable=self.remote_info_var, justify=tk.LEFT, font=("Consolas", 9)).pack(anchor="w")
        tk.Button(remote_frame, text="Copy phone details", command=self.copy_remote_details).pack(anchor="e")
        self.refresh_remote_info()

    def local_address(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return socket.gethostname()

    def refresh_remote_info(self):
        self.remote_info_var.set(
            f"Computer name: {CONFIG['computer_name']}\n"
            f"Local address: http://{self.local_address()}:{CONFIG['port']}\n"
            f"Access token: {CONFIG['token']}\n"
            f"For mobile data, use this laptop's Tailscale 100.x.x.x address."
        )

    def copy_remote_details(self):
        text = (
            f"Name: {CONFIG['computer_name']}\n"
            f"Address: http://{self.local_address()}:{CONFIG['port']}\n"
            f"Token: {CONFIG['token']}"
        )
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log("Phone connection details copied.")

    def _append_log(self, line):
        self.remote_logs.append(line)
        super()._append_log(line)

    def start_remote(self):
        if self.worker and self.worker.is_alive():
            return {"ok": True, "message": "Already running"}

        try:
            interval = float(self.interval_var.get())
            if interval <= 0:
                raise ValueError
        except ValueError:
            raise RuntimeError("Invalid interval in the Windows application.")

        # A remote Start also begins a brand-new run from page 1.
        self.clear_checkpoint()
        self.stop_event.clear()
        self.pause_event.clear()
        self.stats = {"cycle": 0, "page": 0, "checked": 0, "updated": 0, "skipped": 0, "errors": 0, "current_sku": "", "last_action": ""}
        self.start_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL, text="Pause")
        self.stop_btn.config(state=tk.NORMAL)
        self.worker = threading.Thread(target=self.run_bot, daemon=True)
        self.worker.start()
        self.log("Started from phone remote.")
        return {"ok": True}

    def pause_remote(self):
        if not (self.worker and self.worker.is_alive()):
            return {"ok": True, "message": "Not running"}
        self.pause_event.set()
        self.pause_btn.config(text="Resume")
        self.log("Paused from phone remote.")
        return {"ok": True}

    def resume_remote(self):
        self.pause_event.clear()
        self.pause_btn.config(text="Pause")
        self.log("Resumed from phone remote.")
        return {"ok": True}

    def stop_remote(self):
        self.stop_event.set()
        self.pause_event.clear()
        self.clear_checkpoint()
        self.log("Stop requested from phone remote. The next Start will begin from page 1.")
        return {"ok": True}

    def restart_remote(self):
        self.stop_event.set()
        self.pause_event.clear()
        self.log("Remote restart requested.")
        def delayed_restart():
            if self.worker and self.worker.is_alive():
                self.root.after(500, delayed_restart)
            else:
                self.start_remote()
        self.root.after(1000, delayed_restart)
        return {"ok": True, "message": "Restart scheduled"}

    def remote_status(self):
        alive = bool(self.worker and self.worker.is_alive())
        if alive and self.pause_event.is_set():
            state = "Paused"
        elif alive:
            state = "Running"
        else:
            state = "Ready"
        return {
            "computer_name": CONFIG["computer_name"],
            "address": f"{self.local_address()}:{CONFIG['port']}",
            "state": state,
            "stats": dict(self.stats),
            "dry_run": bool(self.dry_run_var.get()),
            "logs": list(self.remote_logs)[-80:],
        }


class Handler(BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def json_response(self, data, status=200):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def text_response(self, text, status=200):
        raw = text.encode("utf-8")
        self.send_response(status)
        self.cors()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def authorised(self):
        return secrets.compare_digest(
            self.headers.get("Authorization", ""),
            "Bearer " + CONFIG["token"],
        )

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            return self.text_response(MOBILE_HTML)
        if path == "/api/status":
            if not self.authorised():
                return self.json_response({"error": "Unauthorized"}, 401)
            result = {}
            done = threading.Event()

            def collect():
                try:
                    result.update(APP.remote_status())
                finally:
                    done.set()

            APP.root.after(0, collect)
            done.wait(3)
            return self.json_response(result)

        return self.json_response({"error": "Not found"}, 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not self.authorised():
            return self.json_response({"error": "Unauthorized"}, 401)

        actions = {
            "/api/start": APP.start_remote,
            "/api/pause": APP.pause_remote,
            "/api/resume": APP.resume_remote,
            "/api/stop": APP.stop_remote,
            "/api/restart": APP.restart_remote,
        }
        action = actions.get(path)
        if not action:
            return self.json_response({"error": "Not found"}, 404)

        result = {}
        done = threading.Event()

        def run_action():
            try:
                result.update(action())
            except Exception as exc:
                result.update({"ok": False, "error": str(exc)})
            finally:
                done.set()

        APP.root.after(0, run_action)
        done.wait(5)
        return self.json_response(result, 200 if result.get("ok") else 400)

    def log_message(self, format, *args):
        return


def start_server():
    server = ThreadingHTTPServer(("0.0.0.0", int(CONFIG["port"])), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    global APP
    root = tk.Tk()
    APP = RemotePriceMatcherApp(root)
    try:
        start_server()
        APP.log(f"Phone remote server started on port {CONFIG['port']}.")
    except Exception as exc:
        APP.log(f"REMOTE SERVER ERROR: {exc}")
    root.mainloop()


if __name__ == "__main__":
    main()
