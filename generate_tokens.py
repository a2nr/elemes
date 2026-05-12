#!/usr/bin/env python3
"""
Script to generate/update the tokens CSV file based on lessons in the content directory.

If the CSV already exists, new lesson columns are added (with 'not_started')
and existing student data is preserved.  If it doesn't exist, a fresh file
is created with a dummy example row.
"""

import csv
import glob
import os
import re
import stat

# Configuration
CONTENT_DIR = '../content'
TOKENS_FILE = '../tokens_siswa.csv'


def get_lesson_names():
    """Get all lesson names from the content directory (excluding home.md)."""
    home_file_path = os.path.join(CONTENT_DIR, "home.md")
    lesson_names = []

    if os.path.exists(home_file_path):
        with open(home_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Use robust regex to split Available_Lessons
        parts = re.split(r'-{3,}Available_Lessons-{3,}', content)
        if len(parts) > 1:
            lesson_list_content = parts[1]
            # Allow optional leading slash in /lesson/ prefix
            lesson_links = re.findall(
                r'\[([^\]]+)\]\((?:/?lesson/)?([^\)]+)\)', lesson_list_content
            )
            if lesson_links:
                for _link_text, slug in lesson_links:
                    lesson_names.append(slug.replace('.md', ''))
                return lesson_names

    # Fallback: alphabetical order
    lesson_files = glob.glob(os.path.join(CONTENT_DIR, "*.md"))
    for file_path in lesson_files:
        filename = os.path.basename(file_path)
        if filename == "home.md":
            continue
        lesson_names.append(filename.replace('.md', ''))
    lesson_names.sort()
    return lesson_names


def _set_permissions(path):
    """Set rw-rw-rw- so the container can update the file."""
    try:
        cur = os.stat(path).st_mode
        os.chmod(path, cur | stat.S_IRUSR | stat.S_IWUSR
                           | stat.S_IRGRP | stat.S_IWGRP
                           | stat.S_IROTH | stat.S_IWOTH)
        print(f"Set permissions for {path} to allow container access")
    except Exception as e:
        print(f"Warning: Could not set file permissions: {e}")


def generate_tokens_csv():
    """Generate or update the tokens CSV file."""
    lesson_names = get_lesson_names()
    new_headers = ['token', 'nama_siswa'] + lesson_names

    if os.path.exists(TOKENS_FILE):
        # ── Merge mode: preserve existing data, add new columns ──
        with open(TOKENS_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            old_headers = list(reader.fieldnames) if reader.fieldnames else []
            rows = list(reader)

        added_cols = [h for h in new_headers if h not in old_headers]
        removed_cols = [h for h in old_headers if h not in new_headers
                        and h not in ('token', 'nama_siswa')]

        # Rebuild each row with the new header order
        merged_rows = []
        for i, row in enumerate(rows):
            new_row = {}
            for h in new_headers:
                if h in ('token', 'nama_siswa'):
                    # Ambil apa adanya dari baris yang sudah ada
                    new_row[h] = row.get(h, '')
                else:
                    # Baris pertama (index 0) selalu dipaksa completed
                    if i == 0:
                        new_row[h] = 'completed'
                    else:
                        new_row[h] = row.get(h, 'not_started')
            merged_rows.append(new_row)

        with open(TOKENS_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=new_headers, delimiter=';')
            writer.writeheader()
            writer.writerows(merged_rows)

        if added_cols:
            print(f"Kolom baru ditambahkan: {added_cols}")
        if removed_cols:
            print(f"Kolom lama dihapus: {removed_cols}")
        print(f"Updated {TOKENS_FILE} — {len(merged_rows)} siswa dipertahankan.")

    else:
        # ── Fresh mode: create new file ──
        with open(TOKENS_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(new_headers)
            # Add a Guru user by default
            guru_row = ['guru_123', 'Guru'] + ['completed'] * len(lesson_names)
            writer.writerow(guru_row)
            dummy_row = ['dummy_token_12345', 'Example Student'] + \
                        ['not_started'] * len(lesson_names)
            writer.writerow(dummy_row)
        print(f"Created tokens file: {TOKENS_FILE}")
        print("Tambahkan siswa dengan format: token;nama_siswa;status;...")

    _set_permissions(TOKENS_FILE)
    print(f"Headers: {new_headers}")


if __name__ == '__main__':
    generate_tokens_csv()
