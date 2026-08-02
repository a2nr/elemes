#!/usr/bin/env python3
"""
Content Parser for Locust E2E Test Generation.

Scans the content/ directory, parses lesson markdown files,
extracts test-relevant data, and writes test_data.json.

Also injects a LOCUST_TEST token into tokens_siswa.csv if not present.

Usage (from elemes/load-test/):
    python content_parser.py
    python content_parser.py --content-dir ../../content --tokens-file ../../tokens_siswa.csv --num-tokens 50
"""

import argparse
import csv
import json
import os
import re
import sys
import uuid


# ---------------------------------------------------------------------------
# Marker extraction (mirrors lesson_service.py logic)
# ---------------------------------------------------------------------------

def extract_section(content: str, start_marker: str, end_marker: str) -> tuple[str, str]:
    """Extract text between markers. Returns (extracted, remaining)."""
    if start_marker not in content or end_marker not in content:
        return "", content

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return "", content

    extracted = content[start_idx + len(start_marker):end_idx].strip()
    remaining = content[:start_idx] + content[end_idx + len(end_marker):]
    return extracted, remaining


def detect_lesson_type(content: str) -> str:
    """Detect lesson type from markers present in content."""
    has_arduino = '---INITIAL_CODE_ARDUINO---' in content
    has_c = '---INITIAL_CODE---' in content
    has_python = '---INITIAL_PYTHON---' in content
    has_circuit = '---INITIAL_CIRCUIT---' in content
    has_quiz = '---INITIAL_QUIZ---' in content
    has_velxio = '---VELXIO_CIRCUIT---' in content

    if has_arduino or (has_velxio and not has_c and not has_python):
        return 'arduino'
    if has_quiz:
        return 'quiz'
    if has_c and has_circuit:
        return 'hybrid'
    if has_circuit and not has_c and not has_python:
        return 'circuit'
    if has_python and not has_c:
        return 'python'
    return 'c'


def find_lesson_file(content_dir: str, slug: str) -> str | None:
    """Cari file .md dengan slug (basename) di content_dir secara rekursif."""
    target = f'{slug}.md'
    for root, _dirs, files in os.walk(content_dir):
        if target in files:
            return os.path.join(root, target)
    return None


def parse_lesson(filepath: str) -> dict:
    """Parse a single lesson markdown file and extract test data."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    slug = os.path.basename(filepath).replace('.md', '')
    lesson_type = detect_lesson_type(content)

    # Extract all relevant sections
    initial_code_c, _ = extract_section(content, '---INITIAL_CODE---', '---END_INITIAL_CODE---')
    initial_python, _ = extract_section(content, '---INITIAL_PYTHON---', '---END_INITIAL_PYTHON---')
    initial_code_arduino, _ = extract_section(content, '---INITIAL_CODE_ARDUINO---', '---END_INITIAL_CODE_ARDUINO---')
    velxio_circuit, _ = extract_section(content, '---VELXIO_CIRCUIT---', '---END_VELXIO_CIRCUIT---')
    expected_output, _ = extract_section(content, '---EXPECTED_OUTPUT---', '---END_EXPECTED_OUTPUT---')
    expected_output_python, _ = extract_section(content, '---EXPECTED_OUTPUT_PYTHON---', '---END_EXPECTED_OUTPUT_PYTHON---')
    expected_serial, _ = extract_section(content, '---EXPECTED_SERIAL_OUTPUT---', '---END_EXPECTED_SERIAL_OUTPUT---')
    expected_wiring, _ = extract_section(content, '---EXPECTED_WIRING---', '---END_EXPECTED_WIRING---')
    key_text, _ = extract_section(content, '---KEY_TEXT---', '---END_KEY_TEXT---')
    solution_code, _ = extract_section(content, '---SOLUTION_CODE---', '---END_SOLUTION_CODE---')
    solution_python, _ = extract_section(content, '---SOLUTION_PYTHON---', '---END_SOLUTION_PYTHON---')

    # A lesson is compilable if it has solution code or Arduino initial code
    is_compilable = bool(solution_code or solution_python or initial_code_arduino)

    data = {
        'slug': slug,
        'type': lesson_type,
        'has_c': bool(initial_code_c),
        'has_python': bool(initial_python),
        'has_circuit': '---INITIAL_CIRCUIT---' in content,
        'has_arduino': bool(initial_code_arduino),
        'has_velxio': bool(velxio_circuit),
        'compilable': is_compilable,
        'key_text': key_text,
    }

    # Add type-specific fields
    if initial_code_c:
        data['initial_code_c'] = initial_code_c
    if solution_code:
        data['solution_code'] = solution_code
    if initial_python:
        data['initial_python'] = initial_python
    if solution_python:
        data['solution_python'] = solution_python
    if expected_output:
        data['expected_output'] = expected_output
    if expected_output_python:
        data['expected_output_python'] = expected_output_python
    if initial_code_arduino:
        data['initial_code_arduino'] = initial_code_arduino
    if velxio_circuit:
        data['velxio_circuit'] = velxio_circuit
    if expected_serial:
        data['expected_serial'] = expected_serial
    if expected_wiring:
        data['expected_wiring'] = expected_wiring

    return data


def scan_all_lessons(content_dir: str) -> list[str]:
    """Scan recursively for lesson slugs (basename without .md).

    Konten tersimpan di subfolder (dasar/, arduino/, circuit/), sedangkan
    API lesson memakai slug tanpa folder (find_lesson_file mencari di semua
    folder). Sub-home.md bukan lesson, di-skip.
    """
    slugs = []
    for root, _dirs, files in os.walk(content_dir):
        for f in sorted(files):
            if not f.endswith('.md') or f in ('home.md', 'sub-home.md'):
                continue
            slugs.append(f[:-3])
    return sorted(set(slugs))


def get_ordered_slugs(content_dir: str) -> list[str]:
    """Get lesson slugs in order from home.md's Available_Lessons section."""
    home_path = os.path.join(content_dir, 'home.md')
    if not os.path.exists(home_path):
        return []

    with open(home_path, 'r', encoding='utf-8') as f:
        home_content = f.read()

    parts = home_content.split('----Available_Lessons----')
    if len(parts) <= 1:
        # Try alternate separator
        parts = home_content.split('---Available_Lessons---')
    if len(parts) <= 1:
        return []

    links = re.findall(r'\[([^\]]+)\]\((?:\/?lesson\/)?([^\)]+)\)', parts[1])
    return [fn.replace('.md', '') for _, fn in links]


# ---------------------------------------------------------------------------
# Token injection
# ---------------------------------------------------------------------------

def ensure_test_tokens(tokens_file: str, lesson_slugs: list[str], num_tokens: int) -> list[str]:
    """
    Ensure a specified number of test tokens exist in tokens_siswa.csv.
    Returns a list of token strings.
    """
    existing_tokens = []
    rows = []
    fieldnames = []

    if os.path.exists(tokens_file):
        with open(tokens_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        for row in rows:
            if row.get('token', '').startswith('LOCUST_TEST_'):
                existing_tokens.append(row['token'])

    if not fieldnames:
        fieldnames = ['token', 'nama_siswa'] + lesson_slugs

    tokens_to_return = existing_tokens[:num_tokens]
    
    if len(tokens_to_return) < num_tokens:
        needed = num_tokens - len(tokens_to_return)
        new_tokens = []
        for i in range(needed):
            token = f"LOCUST_TEST_{uuid.uuid4().hex[:8]}"
            new_tokens.append(token)
            
            new_row = {'token': token, 'nama_siswa': f"Locust Bot {len(tokens_to_return) + i + 1}"}
            for slug in lesson_slugs:
                if slug not in fieldnames:
                     fieldnames.append(slug)
                new_row[slug] = 'not_started'
            rows.append(new_row)
            
        with open(tokens_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(rows)
            
        print(f"  ✚  Injected {len(new_tokens)} new test tokens.")
        tokens_to_return.extend(new_tokens)
    else:
        print(f"  ♻  Reusing {num_tokens} existing test tokens.")

    return tokens_to_return


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _get_teacher_token(tokens_file: str) -> str:
    """Get the teacher token (first data row)."""
    if not os.path.exists(tokens_file):
        return ""
    with open(tokens_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            return row.get('token', '')
    return ""


def main():
    parser = argparse.ArgumentParser(description='Parse content/ for Locust test generation')
    parser.add_argument('--content-dir', default='../../content',
                        help='Path to content directory (default: ../../content)')
    parser.add_argument('--tokens-file', default='../../tokens_siswa.csv',
                        help='Path to tokens CSV (default: ../../tokens_siswa.csv)')
    parser.add_argument('--num-tokens', type=int, default=50,
                        help='Number of test tokens to generate (default: 50)')
    parser.add_argument('--output', default='test_data.json',
                        help='Output JSON file (default: test_data.json)')
    args = parser.parse_args()

    content_dir = os.path.abspath(args.content_dir)
    tokens_file = os.path.abspath(args.tokens_file)

    print(f"\n{'='*60}")
    print(f"  Elemes Content Parser for Locust E2E Testing")
    print(f"{'='*60}")
    print(f"  Content dir : {content_dir}")
    print(f"  Tokens file : {tokens_file}")
    print(f"  Num tokens  : {args.num_tokens}")
    print(f"  Output      : {args.output}")
    print()

    # 1. Get ordered lesson slugs
    ordered_slugs = get_ordered_slugs(content_dir)
    all_slugs = scan_all_lessons(content_dir)
    if not ordered_slugs:
        # Fallback: recursive scan (konten di subfolder)
        ordered_slugs = all_slugs
    else:
        # Gabungkan: slug dari home.md (urutan) + slug hasil scan yang belum ada
        for s in all_slugs:
            if s not in ordered_slugs:
                ordered_slugs.append(s)

    print(f"  📚 Found {len(ordered_slugs)} lessons:")

    # 2. Parse each lesson
    lessons = []
    for slug in ordered_slugs:
        filepath = find_lesson_file(content_dir, slug)
        if not filepath:
            print(f"     ⚠  {slug}.md not found, skipping")
            continue

        lesson = parse_lesson(filepath)
        lessons.append(lesson)

        # Summary icon per type
        icons = {
            'c': '🔧', 'python': '🐍', 'hybrid': '🔀',
            'circuit': '⚡', 'arduino': '🤖', 'quiz': '❓'
        }
        icon = icons.get(lesson['type'], '📄')
        compilable = '✓ compile' if lesson.get('compilable') else '✗ compile'
        print(f"     {icon} {slug} [{lesson['type']}] {compilable}")

    # 3. Inject test tokens
    print()
    tokens = ensure_test_tokens(tokens_file, ordered_slugs, args.num_tokens)

    # 4. Build output
    test_data = {
        'generated_by': 'content_parser.py',
        'tokens': tokens,
        'teacher_token': _get_teacher_token(tokens_file),
        'lessons': lessons,
        'stats': {
            'total': len(lessons),
            'c': sum(1 for l in lessons if l['type'] == 'c'),
            'python': sum(1 for l in lessons if l['type'] == 'python'),
            'hybrid': sum(1 for l in lessons if l['type'] == 'hybrid'),
            'circuit': sum(1 for l in lessons if l['type'] == 'circuit'),
            'arduino': sum(1 for l in lessons if l['type'] == 'arduino'),
            'quiz': sum(1 for l in lessons if l['type'] == 'quiz'),
            'compilable': sum(1 for l in lessons if l.get('compilable')),
        }
    }

    # 5. Write output
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, indent=2, ensure_ascii=False)

    print(f"\n  ✅ Wrote {args.output}")
    print(f"     {test_data['stats']['total']} lessons "
          f"({test_data['stats']['compilable']} compilable)")
    print(f"\n  Next: locust -f locustfile.py")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
