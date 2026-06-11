# -*- coding: utf-8 -*-
"""
threads-intake enrichment worker.

Scans Alma.Threads/00-raw/inbox for capture notes with `enriched: false`,
transcribes Hebrew voice memos / analyzes photos / summarizes text via Gemini,
appends the result to the note body and writes suggestion fields to frontmatter.

Iron rules honored:
- Never touches `target_vault` (suggestion only - final classification is Assaf's).
- Append-only on the body. Existing user text is never modified.
- Atomic writes (tmp + os.replace). Raw capture survives any failure.
- stdlib only. No ffmpeg needed: Gemini accepts audio/webm inline (proven 11/06/2026).

Usage: python enrich.py [--config path] [--inbox path-override] [--once-name file.md]
"""
import sys, os, json, base64, re, time, urllib.request, urllib.error, pathlib, argparse

# pythonw (the scheduled task) has no stdout - guard all console output.
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")


def say(msg):
    if sys.stdout:
        print(msg)

HERE = pathlib.Path(__file__).parent
LOCK = HERE / "enrich.lock"
LOG = HERE / "enrich-log.jsonl"

MIME = {".webm": "audio/webm", ".ogg": "audio/ogg", ".m4a": "audio/mp4", ".mp3": "audio/mpeg",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif", ".heic": "image/heic"}


def log(event, **kw):
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **kw}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def parse_note(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", text, re.S)
    if not m:
        return None, text
    return m.group(1).splitlines(), text[m.end():]


def fm_get(fm_lines, key):
    for line in fm_lines:
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip()
    return None


def fm_set(fm_lines, key, value):
    for i, line in enumerate(fm_lines):
        if line.startswith(key + ":"):
            fm_lines[i] = f"{key}: {value}"
            return
    fm_lines.append(f"{key}: {value}")


def gemini(cfg, key, parts):
    body = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"response_mime_type": "application/json"},
    }).encode()
    last_err = None
    for model in cfg["models"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode())
            return json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
        except urllib.error.HTTPError as e:
            last_err = f"{model}: HTTP {e.code}"
            if e.code == 429:
                time.sleep(20)  # rate limit - brief pause before trying next model
        except Exception as e:
            last_err = f"{model}: {type(e).__name__}: {e}"
    raise RuntimeError(last_err)


def build_parts(cfg, kind, body_text, media_path):
    vaults = ", ".join(cfg["vaults"])
    base = (
        "אתה מעשיר פריט לכידה במערכת ידע אישית עם 9 וולטים: "
        f"{vaults}. "
        "alma-threads הוא ה-inbox; הצע וולט יעד מהרשימה הסגורה בלבד. "
        'החזר JSON בלבד במבנה: {"transcript": "...", "summary": "...", '
        '"suggested_vault": "...", "suggested_tags": ["..."]} '
        "- transcript: תמליל מלא בעברית (לקול) או תיאור+טקסט-מצולם (לתמונה); לטקסט החזר null. "
        "- summary: שורה אחת בעברית. - suggested_tags: עד 4 תגיות קצרות באנגלית kebab-case."
    )
    parts = [{"text": base}]
    if media_path and media_path.exists():
        mime = MIME.get(media_path.suffix.lower())
        if mime:
            parts.append({"inline_data": {"mime_type": mime,
                          "data": base64.b64encode(media_path.read_bytes()).decode()}})
    if body_text.strip():
        parts.append({"text": "תוכן הפריט:\n" + body_text.strip()[:8000]})
    return parts


def enrich_file(cfg, key, path: pathlib.Path) -> str:
    text = path.read_text(encoding="utf-8")
    fm, body = parse_note(text)
    if fm is None or fm_get(fm, "type") != "capture":
        return "skip:not-capture"
    if fm_get(fm, "enriched") != "false":
        return "skip:already"
    attempts = int(fm_get(fm, "enrich_attempts") or 0)
    if attempts >= cfg["max_attempts"]:
        return "skip:max-attempts"

    kind = fm_get(fm, "capture_kind") or "text"
    media_rel = fm_get(fm, "media")
    media_path = (path.parent / media_rel) if media_rel else None

    try:
        result = gemini(cfg, key, build_parts(cfg, kind, body, media_path))
    except Exception as e:
        fm_set(fm, "enrich_attempts", attempts + 1)
        fm_set(fm, "enrich_error", '"' + str(e).replace('"', "'")[:160] + '"')
        write_atomic(path, fm, body)
        log("error", file=path.name, error=str(e)[:300])
        return "error"

    transcript = result.get("transcript")
    summary = (result.get("summary") or "").strip()
    vault = result.get("suggested_vault") or "alma-threads"
    if vault not in cfg["vaults"]:
        vault = "alma-threads"
    tags = [t for t in (result.get("suggested_tags") or []) if re.fullmatch(r"[a-z0-9-]{2,30}", str(t))][:4]

    additions = ""
    if transcript and kind == "voice" and "## תמליל" not in body:
        additions += f"\n## תמליל\n{transcript.strip()}\n"
    elif transcript and kind == "photo" and "## ניתוח" not in body:
        additions += f"\n## ניתוח\n{transcript.strip()}\n"
    if summary and "## תקציר" not in body:
        additions += f"\n## תקציר\n{summary}\n"

    fm_set(fm, "enriched", "true")
    fm_set(fm, "suggested_vault", vault)
    fm_set(fm, "suggested_tags", "[" + ", ".join(tags) + "]")
    fm_set(fm, "enriched_at", time.strftime("%Y-%m-%d %H:%M"))
    write_atomic(path, fm, body.rstrip("\n") + "\n" + additions)
    log("enriched", file=path.name, vault=vault, tags=tags)
    return "enriched"


def write_atomic(path: pathlib.Path, fm_lines, body):
    content = "---\n" + "\n".join(fm_lines) + "\n---\n" + body
    if not content.endswith("\n"):
        content += "\n"
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "enrich-config.json"))
    ap.add_argument("--inbox", default=None, help="override inbox path (testing)")
    ap.add_argument("--once-name", default=None, help="process a single file by name")
    args = ap.parse_args()

    cfg = json.loads(pathlib.Path(args.config).read_text(encoding="utf-8-sig"))
    if args.inbox:
        cfg["inbox"] = args.inbox
    inbox = pathlib.Path(cfg["inbox"])
    key = pathlib.Path(cfg["gemini_key_path"]).read_text(encoding="utf-8-sig").strip().splitlines()[-1].strip()

    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 600:
        say("lock held - exiting")
        return
    LOCK.write_text(str(os.getpid()))
    calls = 0
    try:
        files = [inbox / args.once_name] if args.once_name else sorted(inbox.glob("*.md"))
        for f in files:
            if not f.exists():
                continue
            name = f.name.lower()
            if "conflict" in name or re.search(r"-[a-z0-9-]*desktop[a-z0-9-]*\.md$", name):
                continue
            if time.time() - f.stat().st_mtime < cfg["min_age_seconds"] and not args.once_name:
                continue
            if calls >= cfg["max_calls_per_run"]:
                say("call cap reached - rest on next run")
                break
            status = enrich_file(cfg, key, f)
            if status in ("enriched", "error"):
                calls += 1
            say(f"{f.name}: {status}")
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
