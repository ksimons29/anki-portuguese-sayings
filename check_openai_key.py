import requests

# 🔐 Replace with the key you want to test
api_key = "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"

headers = {
    "Authorization": f"Bearer {api_key}"
}

response = requests.get("https://api.openai.com/v1/models", headers=headers)

if response.status_code == 200:
    print("✅ API key is VALID.")
else:
    print("❌ Invalid API key.")
    print("Status:", response.status_code)
    print("Message:", response.json().get("error", {}).get("message", "Unknown error"))
