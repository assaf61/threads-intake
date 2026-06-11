# -*- coding: utf-8 -*-
"""One-off transcription of inbox voice captures via Gemini (stdlib only)."""
import sys, json, base64, urllib.request, pathlib

sys.stdout.reconfigure(encoding="utf-8")

KEY_PATH = pathlib.Path(r"C:\Users\owner\OneDrive - עלמא ניהול פרויקטים\OD - Alma\IT\AI\AI - מקומי\Gemini API Key.txt")
MEDIA = pathlib.Path(r"C:\Users\owner\OneDrive - עלמא ניהול פרויקטים\Alma Mind\Alma.Threads\00-raw\inbox\media")

key = KEY_PATH.read_text(encoding="utf-8-sig").strip().splitlines()[-1].strip()

MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]
PROMPT = ("תמלל את ההקלטה הזו לעברית, מילה במילה. אם יש מילים באנגלית השאר אותן באנגלית. "
          "החזר רק את התמליל עצמו, ללא הערות.")

def transcribe(path: pathlib.Path) -> str:
    audio_b64 = base64.b64encode(path.read_bytes()).decode()
    body = json.dumps({
        "contents": [{"parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": "audio/webm", "data": audio_b64}},
        ]}]
    }).encode()
    last_err = None
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode())
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            last_err = f"{model}: HTTP {e.code} {e.read().decode()[:300]}"
        except Exception as e:
            last_err = f"{model}: {e}"
    return f"[שגיאת תמלול: {last_err}]"

for name in sys.argv[1:]:
    p = MEDIA / name
    print(f"\n===== {name} =====")
    print(transcribe(p))
