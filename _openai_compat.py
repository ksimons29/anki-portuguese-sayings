# _openai_compat.py
# Single source of truth for chat completions.
# Supports OpenAI (new SDK) or Azure OpenAI (auto-detect via AZURE_OPENAI_ENDPOINT).
# Includes MOCK mode (set MOCK_LLM=1) to return deterministic JSON without network.

from __future__ import annotations
import os, json, re

def _mock_response(messages):
    # Extract last "Target word: X" from the user prompt
    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break
    m = re.search(r"Target word:\s*(.+)", last_user)
    word_en = (m.group(1).strip() if m else "TEST").strip().strip('"')
    word_pt = word_en  # simple echo for mock
    content = json.dumps({
        "word_en": word_en,
        "word_pt": word_pt,
        "sentence_pt": f"Esta é uma frase de teste com {word_pt} para verificar o pipeline.",
        "sentence_en": f"This is a test sentence with {word_en} to verify the pipeline."
    }, ensure_ascii=False)
    return {"choices": [{"message": {"content": content}}]}

def chat(model, messages, temperature=0.2, top_p=0.95, max_tokens=300):
    if os.getenv("MOCK_LLM") == "1":
        return _mock_response(messages)

    if os.getenv("AZURE_OPENAI_ENDPOINT"):
        # Azure OpenAI path
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
        )
        r = client.chat.completions.create(
            model=model,  # deployment name on Azure
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        return {"choices": [{"message": {"content": r.choices[0].message.content}}]}
    else:
        # OpenAI (public) path – new SDK only
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        r = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        return {"choices": [{"message": {"content": r.choices[0].message.content}}]}
