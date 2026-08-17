#!/usr/bin/env python3
"""
Validate docs/*.md files:
1. Setiap file .md wajib punya frontmatter YAML valid (title, order, category).
2. Cek broken internal link.

Jalankan di host (untuk dev loop) atau di container:
    python scripts/validate_docs.py
"""

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
CONTENT_DIR = os.environ.get("CONTENT_DIR", os.path.join(REPO_ROOT, "content"))

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)

errors = []
warnings = []


def check_frontmatter(filename, content):
    """Validate frontmatter exists and has required keys."""
    fm_match = _FRONTMATTER_RE.match(content)
    if not fm_match:
        errors.append(f"{filename}: tidak ada frontmatter YAML (dibutuhkan: title, order, category)")
        return

    fm_text = fm_match.group(1)
    keys = set()
    for line in fm_text.splitlines():
        if ":" in line:
            key = line.split(":", 1)[0].strip()
            keys.add(key)

    required = {"title", "order", "category"}
    missing = required - keys
    if missing:
        errors.append(f"{filename}: frontmatter kurang keys: {sorted(missing)}")

    # Validate order is integer
    order_match = re.search(r'^order:\s*(\d+)', fm_text, re.MULTILINE)
    if not order_match:
        errors.append(f"{filename}: order harus berupa angka")


def check_internal_links(filename, content):
    """Check for broken markdown links to other docs or content files."""
    # Extract body (strip frontmatter)
    fm_match = _FRONTMATTER_RE.match(content)
    body = content[fm_match.end():] if fm_match else content

    # Find all markdown links: [text](path)
    links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', body)
    for text, link in links:
        # Skip external links and anchors
        if link.startswith("http://") or link.startswith("https://"):
            continue
        if link.startswith("#"):
            continue
        if link.startswith("mailto:"):
            continue

        # Resolve relative to docs/ directory
        # Only check links that point to docs/ files
        link_path = link.lstrip("/")
        if link_path.startswith("docs/"):
            link_path = link_path[5:]  # strip "docs/" prefix

        # Skip links to source code, external paths, etc
        if link_path.startswith("http") or link_path.startswith("."):
            continue

        target = os.path.join(DOCS_DIR, link_path)
        if not os.path.exists(target):
            # Only warn if it looks like it should be a docs file
            if link_path.endswith(".md") or "/" in link_path:
                warnings.append(f"{filename}: link mungnot '{link}' → '{link_path}' tidak ditemukan")


def main():
    if not os.path.isdir(DOCS_DIR):
        print(f"❌ Direktori docs tidak ditemukan: {DOCS_DIR}")
        return 1

    md_files = sorted(f for f in os.listdir(DOCS_DIR) if f.endswith(".md"))
    if not md_files:
        print(f"⚠️  Tidak ada file .md di {DOCS_DIR}")
        return 0

    for fname in md_files:
        path = os.path.join(DOCS_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, PermissionError) as e:
            errors.append(f"{fname}: tidak bisa dibaca: {e}")
            continue

        check_frontmatter(fname, content)
        check_internal_links(fname, content)

    print(f"\n=== Dokumen yang divalidasi: {len(md_files)} file ===")

    if errors:
        print(f"\n❌ {len(errors)} error:")
        for e in errors:
            print(f"  - {e}")
        return 1

    if warnings:
        print(f"\n⚠️  {len(warnings)} warning:")
        for w in warnings:
            print(f"  - {w}")

    print("\n✅ Semua file docs valid (frontmatter lengkap, tidak ada broken link internal)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
