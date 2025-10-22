from __future__ import annotations
import os, json, re, urllib.request

def _mock(messages):
    last = next((m["content"] for m in reversed(messages) if m.get("role")=="user"), "")
    m = re.search(r"Target word:\s*(.+)", last)
    w = (m.group(1).strip().strip('"') if m else "TEST")
    return {"choices":[{"message":{"content":json.dumps({
        "word_en": w, "word_pt": w,
        "sentence_pt": f"Esta é uma frase de teste com {w} para verificar o pipeline.",
        "sentence_en": f"This is a test sentence with {w} to verify the pipeline."
    })}}]}

def _http_chat(model, messages, temperature=0.2, top_p=0.95, max_tokens=300):
    api_key = os.getenv("OPENAI_API_KEY") or ""
    if not api_key: raise RuntimeError("OPENAI_API_KEY not set")
    body = {"model":model,"messages":messages,"temperature":temperature,"top_p":top_p,"max_tokens":max_tokens}
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type":"application/json","Authorization":f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    return {"choices":[{"message":{"content":data["choices"][0]["message"]["content"]}}]}

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
            r = client.chat.completions.create(model=model, messages=messages,
                                               temperature=temperature, top_p=top_p, max_tokens=max_tokens)
            return {"choices":[{"message":{"content":r.choices[0].message.content}}]}
        except ModuleNotFoundError:
            pass  # fall through
    # OpenAI SDK → fallback HTTP
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        r = client.chat.completions.create(model=model, messages=messages,
                                           temperature=temperature, top_p=top_p, max_tokens=max_tokens)
        return {"choices":[{"message":{"content":r.choices[0].message.content}}]}
    except ModuleNotFoundError:
        return _http_chat(model, messages, temperature, top_p, max_tokens)
