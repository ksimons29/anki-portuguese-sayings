
from __future__ import annotations
import json, os, urllib.request
from urllib.error import HTTPError

def _sanitize_key(k: str) -> str:
    if not k:
        return ""
    k = k.strip().replace("\n","").replace("\r","").replace("“","").replace("”","").replace("‘","").replace("’","")
    try:
        k.encode("ascii")
    except UnicodeEncodeError:
        k = k.encode("ascii","ignore").decode("ascii")
    return k

def chat(model: str, messages, temperature=0.2, top_p=0.95, max_tokens=300):
    # Mock path for tests
    if os.getenv("MOCK_LLM") == "1":
        content = json.dumps({
            "word_en":"mock","word_pt":"ensaio",
            "sentence_pt":"Isto é apenas um teste para validar o pipeline.",
            "sentence_en":"This is only a test to validate the pipeline."
        }, ensure_ascii=False)
        return {"choices":[{"message":{"content":content}}],"usage":{},"meta":{"id":"mock"}}

    api_key = _sanitize_key(os.getenv("OPENAI_API_KEY",""))
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")

    base = os.getenv("OPENAI_BASE_URL","https://api.openai.com").rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"

    # Project keys typically require the Responses API
    use_responses = api_key.startswith("sk-proj-") or os.getenv("FORCE_RESPONSES_API") == "1"

    if use_responses:
        url = f"{base}/responses"
        # Flatten chat messages to a single prompt string
        prompt = "\n\n".join(f"{m.get('role','user').upper()}: {m.get('content','')}" for m in messages)
        payload = {
            "model": model,
            "input": prompt,
            "temperature": float(temperature),
            "top_p": float(top_p),
            "max_output_tokens": int(max_tokens),
        }
    else:
        url = f"{base}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": float(temperature),
            "top_p": float(top_p),
            "max_tokens": int(max_tokens),
        }

    project_id = _sanitize_key(os.getenv("OPENAI_PROJECT",""))
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

    # Normalize shape to look like Chat Completions for the caller
    if isinstance(js, dict) and "choices" in js and js["choices"] and "message" in js["choices"][0]:
        content = js["choices"][0]["message"]["content"]
        usage = js.get("usage",{}); meta={"id":js.get("id")}
    else:
        content = js.get("output_text") or ""
        if not content:
            parts=[]
            for blk in js.get("output",[]):
                if isinstance(blk,dict):
                    for el in blk.get("content",[]):
                        t = el.get("text") or el.get("output_text")
                        if t: parts.append(t)
            content = "\n".join(parts).strip()
        usage = js.get("usage",{}); meta={"id":js.get("id")}
    return {"choices":[{"message":{"content":content}}],"usage":usage,"meta":meta}
