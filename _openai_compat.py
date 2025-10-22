from __future__ import annotations
import os, json, re, urllib.request

def _mock(messages):
    last = next((m["content"] for m in reversed(messages) if m.get("role")=="user"), "")
    m = re.search(r"Target word:\s*(.+)", last)
    w = (m.group(1).strip().strip('"') if m else "TEST")
    # ADD: include fake usage + meta so the caller always has the same keys
    return {
        "choices":[{"message":{"content":json.dumps({
            "word_en": w, "word_pt": w,
            "sentence_pt": f"Esta é uma frase de teste com {w} para verificar o pipeline.",
            "sentence_en": f"This is a test sentence with {w} to verify the pipeline."
        })}}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "meta":  {"model": "mock", "id": None, "created": None, "request_id": "MOCK"}
    }

def _http_chat(model, messages, temperature=0.2, top_p=0.95, max_tokens=300):
    api_key = os.getenv("OPENAI_API_KEY") or ""
    if not api_key: raise RuntimeError("OPENAI_API_KEY not set")
    body = {"model":model,"messages":messages,"temperature":temperature,"top_p":top_p,"max_tokens":max_tokens}
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type":"application/json","Authorization":f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode()
        data = json.loads(raw)
        # ADD: pull headers & usage from raw HTTP response
        hdr = r.info()
        request_id   = hdr.get("x-request-id") or hdr.get("x-ms-request-id")
        processing_ms= hdr.get("openai-processing-ms")
    return {
        "choices":[{"message":{"content":data["choices"][0]["message"]["content"]}}],
        "usage": data.get("usage", {}),
        "meta": {
            "model":   data.get("model"),
            "id":      data.get("id"),
            "created": data.get("created"),
            "request_id": request_id,
            "processing_ms": processing_ms
        }
    }

def chat(model, messages, temperature=0.2, top_p=0.95, max_tokens=300):
    if os.getenv("MOCK_LLM") == "1": return _mock(messages)

    # Azure path (if SDK present)
    if os.getenv("AZURE_OPENAI_ENDPOINT"):
        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION","2024-08-01-preview"),
            )
            r = client.chat.completions.create(
                model=model, messages=messages,
                temperature=temperature, top_p=top_p, max_tokens=max_tokens
            )
            # ADD: forward usage/meta
            usage = getattr(r, "usage", None) or {}
            return {
                "choices":[{"message":{"content":r.choices[0].message.content}}],
                "usage": {
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),
                    "completion_tokens": getattr(usage, "completion_tokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None),
                },
                "meta": {"model": r.model, "id": getattr(r, "id", None), "created": getattr(r, "created", None)}
            }
        except ModuleNotFoundError:
            pass  # fall through

    # OpenAI SDK → fallback HTTP
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        r = client.chat.completions.create(
            model=model, messages=messages,
            temperature=temperature, top_p=top_p, max_tokens=max_tokens
        )
        # ADD: forward usage/meta
        u = getattr(r, "usage", None) or {}
        return {
            "choices":[{"message":{"content":r.choices[0].message.content}}],
            "usage": {
                "prompt_tokens": getattr(u, "prompt_tokens", None),
                "completion_tokens": getattr(u, "completion_tokens", None),
                "total_tokens": getattr(u, "total_tokens", None),
            },
            "meta": {"model": r.model, "id": getattr(r, "id", None), "created": getattr(r, "created", None)}
        }
    except ModuleNotFoundError:
        return _http_chat(model, messages, temperature, top_p, max_tokens)
