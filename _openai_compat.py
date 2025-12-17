
from __future__ import annotations
import json, os, urllib.request
from urllib.error import HTTPError

from keychain_utils import get_api_key, get_project_id, sanitize_key

def chat(model: str, messages, temperature=0.2, top_p=0.95, max_tokens=300):
    # Mock path for tests
    if os.getenv("MOCK_LLM") == "1":
        content = json.dumps({
            "word_en":"mock","word_pt":"ensaio",
            "sentence_pt":"Isto é apenas um teste para validar o pipeline.",
            "sentence_en":"This is only a test to validate the pipeline."
        }, ensure_ascii=False)
        return {"choices":[{"message":{"content":content}}],"usage":{},"meta":{"id":"mock"}}

    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "OpenAI API key not found. "
            "Set OPENAI_API_KEY env var or store in Keychain: "
            'security add-generic-password -a "$USER" -s "anki-tools-openai" -w "sk-..." -U'
        )

    base = os.getenv("OPENAI_BASE_URL","https://api.openai.com").rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"

    # Use standard Chat Completions API for all keys (including project-scoped)
    # Project ID is passed via OpenAI-Project header below
    url = f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "top_p": float(top_p),
        "max_tokens": int(max_tokens),
    }

    project_id = get_project_id()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept-Charset": "utf-8",
        "User-Agent": "anki-tools/utf8-compat",
    }
    if project_id:
        headers["OpenAI-Project"] = project_id

    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            js = json.loads(r.read().decode("utf-8","strict"))
    except HTTPError as err:
        body = ""
        try:
            body = err.read().decode("utf-8", "replace")
        except Exception:
            body = str(err.reason)
        detail = body.strip() or str(err.reason)
        raise RuntimeError(f"OpenAI request failed ({err.code}): {detail}") from err

    # Standard Chat Completions response format
    if not (isinstance(js, dict) and "choices" in js and js["choices"]):
        raise RuntimeError(f"Unexpected response format from OpenAI: {json.dumps(js)[:200]}")

    content = js["choices"][0].get("message", {}).get("content", "")
    usage = js.get("usage", {})
    meta = {"id": js.get("id")}

    return {"choices": [{"message": {"content": content}}], "usage": usage, "meta": meta}
