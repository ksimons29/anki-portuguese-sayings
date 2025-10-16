import os

def compat_chat(messages, model="gpt-4o-mini", **kwargs):
    """
    Works with project keys (sk-proj-...) and classic keys.
    Returns: {"choices":[{"message":{"content": "..."} }]} like the old client.
    """
    try:
        from openai import OpenAI  # new SDK
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        r = client.chat.completions.create(model=model, messages=messages, **kwargs)
        return {"choices":[{"message":{"content": r.choices[0].message.content}}]}
    except Exception:
        import openai  # legacy fallback
        openai.api_key = os.environ["OPENAI_API_KEY"]
        return openai.ChatCompletion.create(model=model, messages=messages, **kwargs)
