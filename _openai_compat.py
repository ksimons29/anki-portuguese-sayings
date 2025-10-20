import os

# If the new SDK (>=1.0) is present, use it exclusively.
try:
    from openai import OpenAI  # new SDK
    def compat_chat(model, messages, temperature=0.2, top_p=0.95, max_tokens=300):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        r = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        return {"choices":[{"message":{"content": r.choices[0].message.content}}]}
except ImportError:
    # Legacy SDK (<=0.28) fallback only if the new class cannot be imported.
    import openai  # type: ignore
    def compat_chat(model, messages, temperature=0.2, top_p=0.95, max_tokens=300):
        if os.getenv("OPENAI_API_KEY"):
            openai.api_key = os.getenv("OPENAI_API_KEY")
        r = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        return {"choices":[{"message":{"content": r['choices'][0]['message']['content']}}]}
