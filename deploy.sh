#!/usr/bin/env bash
# Deploy script - ensures anki-tools always uses the latest version from git repo
#
# This script creates symlinks from ~/anki-tools/ to the canonical versions in the git repo
# Run this after: git pull, major changes, or if you suspect sync issues

set -e

REPO_DIR="$HOME/anki-portuguese-sayings"
DEPLOY_DIR="$HOME/anki-tools"

echo "🚀 Deploying from $REPO_DIR to $DEPLOY_DIR"
echo ""

# Scripts that should be symlinked (canonical version is in the repo)
SCRIPTS=(
    "generate_dashboard_html.py"
)

cd "$DEPLOY_DIR"

for script in "${SCRIPTS[@]}"; do
    echo "📝 Checking $script..."

    # Check if it exists in the repo
    if [ ! -f "$REPO_DIR/$script" ]; then
        echo "   ⚠️  Warning: $script not found in repo, skipping"
        continue
    fi

    # If it exists and is a regular file (not symlink), back it up
    if [ -f "$script" ] && [ ! -L "$script" ]; then
        echo "   📦 Backing up existing file to ${script}.backup"
        mv "$script" "${script}.backup"
    fi

    # If it's already a symlink, remove it
    if [ -L "$script" ]; then
        rm "$script"
    fi

    # Create the symlink
    ln -s "$REPO_DIR/$script" "$script"
    echo "   ✅ Symlinked to repo version"
done

echo ""
echo "✨ Deployment complete!"
echo ""
echo "📋 Summary:"
echo "   • Source of truth: $REPO_DIR (git repo)"
echo "   • Running location: $DEPLOY_DIR (symlinks)"
echo "   • Make changes in: $REPO_DIR"
echo "   • Commit and push: cd $REPO_DIR && git add . && git commit && git push"
echo ""
echo "🔄 To sync after git pull, just run: $REPO_DIR/deploy.sh"
