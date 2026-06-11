# -*- coding: utf-8 -*-
"""Fallback transcription via alternate Gemini models (separate quota buckets)."""
import sys, json, base64, urllib.request, pathlib

sys.stdout.reconfigure(encoding="utf-8")

KEY_PATH = pathlib.Path(r"C:\Users\owner\OneDrive - עלמא ניהול פרויקטים\OD - Alma\IT\AI\AI - מקומי\Gemini API Key.txt")
MEDIA = pathlib.Path(r"C:\Users\owner\OneDrive - עלמא ניהול פרויקטים\Alma Mind\Alma.Threads\00-raw\inbox\media")
MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-1.5-flash"]

key = KEY_PATH.read_text(encoding="utf-8-sig").strip().splitlines()[-1].strip()
audio = MEDIA / sys.argv[1]
body = json.dumps({"contents": [{"parts": [
    {"text": "תמלל את ההקלטה לעברית, מילה במילה. החזר רק את התמליל."},
    {"inline_data": {"mime_type": "audio/webm", "data": base64.b64encode(audio.read_bytes()).decode()}},
]}]}).encode()

for model in MODELS:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}), timeout=120) as r:
            data = json.loads(r.read().decode())
        print(f"[{model}]")
        print(data["candidates"][0]["content"]["parts"][0]["text"].strip())
        break
    except Exception as e:
        print(f"{model}: {e}")
