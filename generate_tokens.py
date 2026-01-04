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
        
    print(f"Created tokens file: {TOKENS_FILE} with headers: {headers}")
    print("Teachers can now add student tokens and names directly to this file.")

if __name__ == '__main__':
    generate_tokens_csv()
