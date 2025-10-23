from __future__ import annotations
import json, os, urllib.request

def chat(model: str, messages, temperature=0.2, top_p=0.95, max_tokens=300):
    # Minimal UTF-8 safe chat wrapper. If MOCK_LLM=1, returns a deterministic mock.
    if os.getenv("MOCK_LLM") == "1":
        content = json.dumps({
            "word_en": "mock", "word_pt": "ensaio",
            "sentence_pt": "Isto é apenas um teste para validar o pipeline.",
            "sentence_en": "This is only a test to validate the pipeline."
        }, ensure_ascii=False)
        return {"choices":[{"message":{"content": content}}],
                "usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2},
                "meta":{"id":"mock","created":0}}

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing (or set MOCK_LLM=1 for offline test)")

    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    url  = f"{base.rstrip('/')}/chat/completions"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "top_p": float(top_p),
        "max_tokens": int(max_tokens),
    }
    # CRITICAL: ensure_ascii=False + explicit UTF-8 bytes
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {api_key}",
            "Accept-Charset": "utf-8",
            "User-Agent": "anki-tools/utf8-compat",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8", "strict")
    js = json.loads(raw)

    content = js["choices"][0]["message"]["content"]
    return {
        "choices": [{"message": {"content": content}}],
        "usage": js.get("usage", {}),
        "meta": {"id": js.get("id"), "created": js.get("created")},
    }
