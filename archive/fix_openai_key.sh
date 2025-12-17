#!/bin/bash
# Fix OpenAI API key issues once and for all

set -e

echo "=== OpenAI API Key Diagnostic & Fix ==="
echo ""

USER_NAME=$(whoami)

# Check current key
echo "[1/4] Checking current API key in Keychain..."
if KEY=$(security find-generic-password -a "$USER_NAME" -s "anki-tools-openai" -w 2>/dev/null); then
    KEY_PREFIX="${KEY:0:10}"
    echo "      Found key: $KEY_PREFIX..."

    if [[ "$KEY" == sk-proj-* ]]; then
        echo "      ⚠ This is a PROJECT-SCOPED key (sk-proj-...)"
        echo "      These keys require additional setup!"
        KEY_TYPE="project"
    else
        echo "      ✓ This is a regular API key"
        KEY_TYPE="regular"
    fi
else
    echo "      ✗ No API key found in Keychain"
    KEY_TYPE="missing"
fi

echo ""

# Check project ID if needed
if [[ "$KEY_TYPE" == "project" ]]; then
    echo "[2/4] Checking for project ID (required for sk-proj- keys)..."
    if PROJ_ID=$(security find-generic-password -a "$USER_NAME" -s "anki-tools-openai-project" -w 2>/dev/null); then
        echo "      ✓ Found project ID: ${PROJ_ID:0:15}..."
    else
        echo "      ✗ No project ID found!"
        echo ""
        echo "=== SOLUTION 1: Add Project ID ==="
        echo "Your key is a project-scoped key and needs a project ID."
        echo ""
        echo "1. Go to: https://platform.openai.com/settings/organization/projects"
        echo "2. Find your project"
        echo "3. Copy the Project ID (starts with 'proj-')"
        echo "4. Run this command:"
        echo ""
        echo "   security add-generic-password -a \"$USER_NAME\" -s \"anki-tools-openai-project\" -w 'proj-YOUR_PROJECT_ID' -U"
        echo ""
        echo "=== SOLUTION 2: Use a Regular API Key (RECOMMENDED) ==="
        echo "Project keys are more complex. Use a regular key instead:"
        echo ""
        echo "1. Go to: https://platform.openai.com/api-keys"
        echo "2. Click 'Create new secret key'"
        echo "3. Name it: 'Anki Portuguese Tools'"
        echo "4. Leave 'Permissions' as default (All)"
        echo "5. Leave 'Project' as default (or select your project)"
        echo "6. Click 'Create secret key'"
        echo "7. Copy the key (starts with 'sk-' but NOT 'sk-proj-')"
        echo "8. Run this command:"
        echo ""
        echo "   security add-generic-password -a \"$USER_NAME\" -s \"anki-tools-openai\" -w 'YOUR_NEW_KEY' -U"
        echo ""
        exit 1
    fi
else
    echo "[2/4] Project ID check skipped (not needed for regular keys)"
fi

echo ""
echo "[3/4] Testing API key with OpenAI..."

# Test the key
if [[ "$KEY_TYPE" == "project" ]]; then
    # Test with project ID
    RESPONSE=$(curl -s https://api.openai.com/v1/models \
        -H "Authorization: Bearer $KEY" \
        -H "OpenAI-Project: $PROJ_ID" 2>&1)
else
    # Test without project ID
    RESPONSE=$(curl -s https://api.openai.com/v1/models \
        -H "Authorization: Bearer $KEY" 2>&1)
fi

if echo "$RESPONSE" | grep -q '"object": "list"'; then
    echo "      ✓ API key is VALID!"
    echo ""
    echo "[4/4] Summary"
    echo "      • Key type: $KEY_TYPE"
    if [[ "$KEY_TYPE" == "project" ]]; then
        echo "      • Project ID: configured"
    fi
    echo "      • Status: ✓ WORKING"
    echo ""
    echo "=== ALL GOOD! You can now run the pipeline ==="
    exit 0
else
    echo "      ✗ API key is INVALID or EXPIRED!"
    echo ""
    echo "Response from OpenAI:"
    echo "$RESPONSE" | head -20
    echo ""
    echo "=== FIX REQUIRED ==="
    echo ""
    echo "Your API key is not working. Please create a NEW key:"
    echo ""
    echo "1. Go to: https://platform.openai.com/api-keys"
    echo "2. Click 'Create new secret key'"
    echo "3. Name it: 'Anki Portuguese Tools'"
    echo "4. Make sure to create a REGULAR key (NOT project-scoped)"
    echo "5. Copy the new key"
    echo "6. Run this command to update Keychain:"
    echo ""
    echo "   security add-generic-password -a \"$USER_NAME\" -s \"anki-tools-openai\" -w 'YOUR_NEW_KEY' -U"
    echo ""
    echo "7. Then run this script again to verify:"
    echo ""
    echo "   ./fix_openai_key.sh"
    echo ""
    exit 1
fi
