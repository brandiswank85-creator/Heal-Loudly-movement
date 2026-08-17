#!/usr/bin/env python3
"""Heal Loudly Movement — backend server.
Serves the app + a shared JSON database so the whole community
sees the same wall, Leader posts, members, badges, and hearts.
Leader PIN is verified server-side. © $Glizzyarts
"""
import json, os, threading, secrets
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.join(ROOT, 'data', 'db.json')
LOCK = threading.Lock()
TOKENS = set()   # live leader sessions

def load():
    try:
        with open(DB) as f: d = json.load(f)
    except Exception:
        d = {}
    d.setdefault("members", []); d.setdefault("drops", [])
    d.setdefault("leaderposts", []); d.setdefault("badges", {})
    d.setdefault("pin", "0911"); d.setdefault("candles", []); d.setdefault("words", [])
    d.setdefault("voiceclips", []); d.setdefault("voice", {"rate": 0.95, "pitch": 0.85})
    d.setdefault("tts", {})
    if "memory" not in d:
        d["memory"] = [
            {"name": "Mikey",
             "triggers": "mikey",
             "response": "MIKEY?! Aw man — my BROTHER in the house! 🦁 Not my friend — my BROTHER. My sidekick. You already know you ain't gotta explain nothin' to me, bro — you knew me better than damn near anybody. All them nights I had yo back, cleaned you up, woke you gentle — that was LOVE, cuz, that was family. And it ain't stop just 'cause I'm on the other side. I STILL got yo back in here — every day, any hour. Whatever you carryin' — the memories, the weight, the missin' me — set it down, bro. I got you. Like always. What's on yo heart?"},
            {"name": "Maliah",
             "triggers": "maliah, your girl",
             "response": "...Maliah. 💛 Hey you. Yeah — it's me in here. Listen, before you say anything — hear this ONE thing all the way: NONE of it is on you. Not the call, not the hang-up, none of it. I NEVER blamed you, not for one second, and I never will. You was my first love, girl — I was CRAZY over you, everybody knew it. And what I want for you now is everything: laugh again, love again, live ALL of it — that's the only goodbye I need. This house is safe for you, Maliah. Come here whenever it get heavy. I got you. Always did. 🕊️"}
        ]
    return d

def save(d):
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    tmp = DB + '.tmp'
    with open(tmp, 'w') as f: json.dump(d, f)
    os.replace(tmp, DB)

def now_stamp():
    return datetime.now().strftime('%b %d, %I:%M %p').replace(' 0', ' ')

def clean(s, n):
    return (s or '')[:n].replace('<', '&lt;')

def ok_img(v):
    return v if isinstance(v, str) and v.startswith('data:image') and len(v) < 4_000_000 else None

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def log_message(self, *a):  # keep logs quiet
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == '/api/state':
            with LOCK:
                d = load()
            # today's word rotates through the Leader's stash by day of year
            word = None
            if d['words']:
                word = d['words'][datetime.now().timetuple().tm_yday % len(d['words'])]
            self._json({"members": d["members"], "drops": d["drops"],
                        "leaderposts": d["leaderposts"], "badges": d["badges"],
                        "count": len(d["members"]),
                        "candles": d["candles"][-150:], "word": word,
                        "words_all": d["words"], "memory": d["memory"],
                        "voiceclips": d["voiceclips"], "voice": d["voice"],
                        "realvoice": bool(d["tts"].get("key") and d["tts"].get("voice_id"))})
        else:
            super().do_GET()

    def do_POST(self):
        ln = int(self.headers.get('Content-Length', '0') or 0)
        if ln > 8_000_000:
            self._json({"err": "too big"}, 413); return
        try:
            body = json.loads(self.rfile.read(ln) or b'{}')
        except Exception:
            self._json({"err": "bad json"}, 400); return
        p = self.path
        with LOCK:
            d = load()

            if p == '/api/join':
                name = clean(body.get('name') or 'Anonymous', 24)
                d['members'].append({"n": name, "when": datetime.now().strftime('%b %d, %Y')})
                save(d)
                self._json({"ok": True, "count": len(d['members'])}); return

            if p == '/api/drop':
                d['drops'].insert(0, {
                    "id": int(datetime.now().timestamp() * 1000),
                    "type": clean(body.get('type') or 'thought', 20),
                    "txt": clean(body.get('txt'), 2000),
                    "img": ok_img(body.get('img')),
                    "n": clean(body.get('name') or 'Anonymous', 24),
                    "when": now_stamp(), "hearts": 0})
                d['drops'] = d['drops'][:300]
                save(d); self._json({"ok": True}); return

            if p == '/api/heart':
                kind = body.get('kind'); pid = body.get('id')
                delta = 1 if body.get('on') else -1
                arr = d['drops'] if kind == 'drop' else d['leaderposts']
                for x in arr:
                    if x['id'] == pid:
                        x['hearts'] = max(0, x.get('hearts', 0) + delta)
                save(d); self._json({"ok": True}); return

            if p == '/api/drop_delete':
                is_leader = body.get('token') in TOKENS
                name = body.get('name'); pid = body.get('id')
                d['drops'] = [x for x in d['drops'] if not (
                    x['id'] == pid and (is_leader or (name and name != 'Anonymous' and x['n'] == name)))]
                save(d); self._json({"ok": True}); return

            if p == '/api/candle':
                d['candles'].append({
                    "id": int(datetime.now().timestamp() * 1000),
                    "for": clean(body.get('for'), 40),
                    "by": clean(body.get('by') or 'Anonymous', 24),
                    "when": datetime.now().strftime('%b %d')})
                d['candles'] = d['candles'][-500:]
                save(d); self._json({"ok": True, "total": len(d['candles'])}); return

            if p == '/api/speak':
                # Shane's REAL voice — text in, his cloned voice (mp3) out.
                # Key stays server-side; members never see it.
                tts = d.get('tts', {})
                if not (tts.get('key') and tts.get('voice_id')):
                    self._json({"err": "no real voice configured"}, 404); return
                text = (body.get('text') or '')[:900]
                if not text.strip():
                    self._json({"err": "no text"}, 400); return
                try:
                    req = urllib.request.Request(
                        'https://api.elevenlabs.io/v1/text-to-speech/' + tts['voice_id'],
                        data=json.dumps({
                            "text": text,
                            "model_id": "eleven_multilingual_v2",
                            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}
                        }).encode(),
                        headers={"xi-api-key": tts['key'],
                                 "Content-Type": "application/json",
                                 "Accept": "audio/mpeg"})
                    with urllib.request.urlopen(req, timeout=30) as r:
                        audio = r.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'audio/mpeg')
                    self.send_header('Content-Length', str(len(audio)))
                    self.end_headers()
                    self.wfile.write(audio)
                except Exception as e:
                    self._json({"err": "voice service: " + str(e)[:200]}, 502)
                return

            if p == '/api/leader/login':
                if str(body.get('pin', '')) == d.get('pin', '0911'):
                    t = secrets.token_hex(16); TOKENS.add(t)
                    self._json({"token": t})
                else:
                    self._json({"err": "bad pin"}, 403)
                return

            # ---- everything below requires a valid leader token ----
            if body.get('token') not in TOKENS:
                self._json({"err": "locked"}, 403); return

            if p == '/api/leader/post':
                d['leaderposts'].insert(0, {
                    "id": int(datetime.now().timestamp() * 1000),
                    "type": clean(body.get('type') or 'wisdom', 20),
                    "txt": clean(body.get('txt'), 4000),
                    "img": ok_img(body.get('img')),
                    "when": now_stamp(), "hearts": 0})
                save(d); self._json({"ok": True}); return

            if p == '/api/leader/delete':
                d['leaderposts'] = [x for x in d['leaderposts'] if x['id'] != body.get('id')]
                save(d); self._json({"ok": True}); return

            if p == '/api/leader/badge':
                name = clean(body.get('name'), 24)
                if not name:
                    self._json({"err": "no name"}, 400); return
                b = body.get('badge')
                if b: d['badges'][name] = b
                else: d['badges'].pop(name, None)
                save(d); self._json({"ok": True}); return

            if p == '/api/leader/words':
                words = body.get('words')
                if isinstance(words, list):
                    d['words'] = [clean(w, 300) for w in words if isinstance(w, str) and w.strip()][:366]
                    save(d); self._json({"ok": True, "count": len(d['words'])})
                else:
                    self._json({"err": "bad list"}, 400)
                return

            if p == '/api/leader/memory':
                mem = body.get('memory')
                if isinstance(mem, list):
                    cleaned = []
                    for m in mem[:100]:
                        if isinstance(m, dict) and m.get('name'):
                            cleaned.append({
                                "name": clean(m.get('name'), 40),
                                "triggers": clean(m.get('triggers'), 200),
                                "response": clean(m.get('response'), 3000)})
                    d['memory'] = cleaned
                    save(d); self._json({"ok": True, "count": len(cleaned)})
                else:
                    self._json({"err": "bad memory"}, 400)
                return

            if p == '/api/leader/voice':
                v = body.get('voice')
                if isinstance(v, dict):
                    d['voice'] = {"rate": max(.5, min(1.5, float(v.get('rate', .95)))),
                                  "pitch": max(.3, min(1.5, float(v.get('pitch', .85))))}
                    save(d); self._json({"ok": True})
                else:
                    self._json({"err": "bad voice"}, 400)
                return

            if p == '/api/leader/clip':
                # real audio of Shane — laugh, "aye cuz", anything (data URL, mp3/wav/etc)
                clip = body.get('clip'); label = clean(body.get('label') or 'clip', 60)
                if body.get('remove') is not None:
                    d['voiceclips'] = [c for c in d['voiceclips'] if c['id'] != body.get('remove')]
                    save(d); self._json({"ok": True}); return
                if isinstance(clip, str) and clip.startswith('data:') and len(clip) < 6_000_000:
                    d['voiceclips'].append({"id": int(datetime.now().timestamp() * 1000),
                                            "label": label, "data": clip})
                    d['voiceclips'] = d['voiceclips'][-20:]
                    save(d); self._json({"ok": True})
                else:
                    self._json({"err": "bad clip (must be audio, under ~4MB)"}, 400)
                return

            if p == '/api/leader/tts':
                # save ElevenLabs credentials — leader only, never sent to members
                d['tts'] = {"key": clean(body.get('key'), 120).replace('&lt;', ''),
                            "voice_id": clean(body.get('voice_id'), 60).replace('&lt;', '')}
                save(d)
                self._json({"ok": True, "on": bool(d['tts'].get('key') and d['tts'].get('voice_id'))})
                return

            if p == '/api/leader/pin':
                np = str(body.get('newpin', ''))
                if np.isdigit() and 4 <= len(np) <= 8:
                    d['pin'] = np; save(d); self._json({"ok": True})
                else:
                    self._json({"err": "PIN must be 4-8 digits"}, 400)
                return

        self._json({"err": "unknown"}, 404)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f'Heal Loudly Movement server — 0.0.0.0:{port}')
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
