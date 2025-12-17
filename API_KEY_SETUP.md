# OpenAI API Key Setup

This document explains how to configure your OpenAI API key for the anki-tools project.

## Storage Method: macOS Keychain

The project uses **macOS Keychain** as the single source of truth for storing the OpenAI API key. This is secure, future-proof, and integrates with macOS's native credential management.

### Why Keychain?

- **Secure**: Keys are encrypted at rest
- **Convenient**: Accessible to all scripts without hardcoding
- **Standard**: Uses macOS built-in security infrastructure
- **Shareable**: Works across terminal sessions and GUI apps

## Initial Setup

### 1. Add your API key to Keychain

```bash
security add-generic-password -a "$USER" -s "anki-tools-openai" -w "sk-your-api-key-here" -U
```

Replace `sk-your-api-key-here` with your actual OpenAI API key.

### 2. (Optional) Add project ID for project-scoped keys

If you're using a project-scoped API key (`sk-proj-...`), you may also want to store the project ID:

```bash
security add-generic-password -a "$USER" -s "anki-tools-openai-project" -w "proj_your-project-id" -U
```

### 3. Verify the key is stored

```bash
security find-generic-password -a "$USER" -s "anki-tools-openai" -w
```

This should print your API key.

## Changing the API Key

To update an existing key, use the same command with the `-U` flag (update):

```bash
security add-generic-password -a "$USER" -s "anki-tools-openai" -w "sk-new-api-key" -U
```

The `-U` flag updates the password if it already exists.

## Deleting the API Key

To remove the key from Keychain:

```bash
security delete-generic-password -a "$USER" -s "anki-tools-openai"
```

## Keychain Service Names

| Service Name | Purpose |
|-------------|---------|
| `anki-tools-openai` | OpenAI API key (required) |
| `anki-tools-openai-project` | Project ID (optional) |

## Troubleshooting

### "Missing Keychain item" error

Ensure you've added the key with the correct service name:

```bash
security add-generic-password -a "$USER" -s "anki-tools-openai" -w "sk-..." -U
```

### Key has special characters or newlines

The scripts automatically sanitize keys by removing:
- Newlines (`\n`, `\r`)
- Smart quotes (`"`, `"`, `'`, `'`)
- Non-ASCII characters

If you pasted a key with formatting issues, delete and re-add it:

```bash
security delete-generic-password -a "$USER" -s "anki-tools-openai"
security add-generic-password -a "$USER" -s "anki-tools-openai" -w "sk-..." -U
```

### Verifying the key works

Test your API key directly:

```bash
curl -s -H "Authorization: Bearer $(security find-generic-password -a "$USER" -s "anki-tools-openai" -w)" \
     https://api.openai.com/v1/models | head -c 200
```

A successful response will show model data. An error indicates an invalid key.

## Architecture

All Python scripts use the shared `keychain_utils.py` module:

```python
from keychain_utils import get_api_key, require_api_key

# Get key (returns None if not found)
key = get_api_key()

# Get key or raise error with setup instructions
key = require_api_key()
```

**Important:** Environment variables like `OPENAI_API_KEY` are **ignored** by the Python scripts to prevent issues with stale/cached keys. Keychain is the only source of truth.
