#!/usr/bin/env python3
"""
Script to generate the tokens CSV file based on lessons in the content directory
"""

import os
import csv
import glob
import uuid

# Configuration
CONTENT_DIR = '../content'
TOKENS_FILE = '../tokens_siswa.csv'

def get_lesson_names():
    """Get all lesson names from the content directory (excluding home.md)"""
    lesson_files = glob.glob(os.path.join(CONTENT_DIR, "*.md"))
    lesson_names = []
    
    for file_path in lesson_files:
        filename = os.path.basename(file_path)
        # Skip home.md as it's not a lesson
        if filename == "home.md":
            continue
        lesson_names.append(filename.replace('.md', ''))
    
    return lesson_names

def generate_tokens_csv():
    """Generate the tokens CSV file with headers and lesson columns"""
    lesson_names = get_lesson_names()

    # Create the file with headers
    headers = ['token', 'nama_siswa'] + lesson_names

    with open(TOKENS_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=';')
        writer.writerow(headers)

        # Add a dummy example row for reference
        dummy_row = ['dummy_token_12345', 'Example Student'] + ['not_started'] * len(lesson_names)
        writer.writerow(dummy_row)

    # Set file permissions to allow read/write access for all users
    # This ensures the container can update the file when progress is tracked
    try:
        import stat
        import os
        current_permissions = os.stat(TOKENS_FILE).st_mode
        os.chmod(TOKENS_FILE, current_permissions | stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
        print(f"Set permissions for {TOKENS_FILE} to allow container access")
    except Exception as e:
        print(f"Warning: Could not set file permissions: {e}")

    print(f"Created tokens file: {TOKENS_FILE} with headers: {headers}")
    print("Teachers can now add student tokens and names directly to this file.")
    print("An example row has been added with token 'dummy_token_12345' for reference.")
    print("To add new students, add new rows with format: token;nama_siswa;lesson1_status;lesson2_status;...")

if __name__ == '__main__':
    generate_tokens_csv()
