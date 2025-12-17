#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Centralized API key management for anki-tools.

This module provides a single, consistent way to access the OpenAI API key
across all scripts in the project.

Storage: macOS Keychain (ONLY source of truth)
- Service name: "anki-tools-openai"
- Optional project ID: "anki-tools-openai-project"

Environment variables are IGNORED to prevent stale key issues.
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional

# Keychain service names (single source of truth)
KEYCHAIN_SERVICE_API_KEY = "anki-tools-openai"
KEYCHAIN_SERVICE_PROJECT = "anki-tools-openai-project"


def _run_security_cmd(service_name: str) -> Optional[str]:
    """Read a password from macOS Keychain."""
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a", os.environ.get("USER", ""),
                "-s", service_name,
                "-w"
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip() or None
    except subprocess.CalledProcessError:
        return None


def sanitize_key(key: str) -> str:
    """
    Remove problematic characters from API keys.

    Handles: newlines, carriage returns, smart quotes, and non-ASCII characters.
    """
    if not key:
        return ""

    # Remove whitespace, newlines, and smart quotes
    key = (
        key.strip()
        .replace("\n", "")
        .replace("\r", "")
        .replace(""", "")
        .replace(""", "")
        .replace("'", "")
        .replace("'", "")
    )

    # Ensure ASCII-only (API keys should be ASCII)
    try:
        key.encode("ascii")
    except UnicodeEncodeError:
        key = key.encode("ascii", "ignore").decode("ascii")

    return key


def get_api_key() -> Optional[str]:
    """
    Get the OpenAI API key from macOS Keychain.

    Keychain is the ONLY source - environment variables are ignored
    to prevent issues with stale/cached keys.

    Returns:
        The sanitized API key, or None if not found.
    """
    key = _run_security_cmd(KEYCHAIN_SERVICE_API_KEY)
    return sanitize_key(key) if key else None


def get_project_id() -> Optional[str]:
    """
    Get the OpenAI project ID from macOS Keychain (optional).

    Keychain is the ONLY source - environment variables are ignored.

    Returns:
        The sanitized project ID, or None if not configured.
    """
    project = _run_security_cmd(KEYCHAIN_SERVICE_PROJECT)
    return sanitize_key(project) if project else None


def require_api_key() -> str:
    """
    Get the API key or raise an error with setup instructions.

    Raises:
        RuntimeError: If the API key is not found in Keychain.

    Returns:
        The sanitized API key.
    """
    key = get_api_key()
    if not key:
        raise RuntimeError(
            "OpenAI API key not found in Keychain.\n\n"
            "To set up your API key, run:\n"
            f'  security add-generic-password -a "$USER" -s "{KEYCHAIN_SERVICE_API_KEY}" -w "sk-..." -U\n\n'
            "To update an existing key, use the same command (the -U flag updates it)."
        )
    return key
