"""
Locust scenario khusus migrasi database (CSV → PostgreSQL).

Menargetkan endpoint yang persistence-nya berubah:
  - /api/login + /api/validate-token   (identitas: CSV → PG users/access_tokens)
  - /api/track-progress                (write progress: CSV → PG student_progress)
  - /api/progress-report.json          (report guru — baca semua siswa)

Data token diambil dari test_data.json (hasilkan dulu:
  python content_parser.py --content-dir ../../content --tokens-file ../../tokens_siswa.csv)

Usage (dari elemes/load-test/):
  locust -f locustfile_db.py
  → set host ke URL Elemes (mis. https://sinau-c-dev.manakin-gentoo.ts.net)
"""

import json
import logging
import os
import random
from pathlib import Path

from locust import HttpUser, between, events, task

TEST_DATA_FILE = Path(__file__).parent / 'test_data.json'
API = os.environ.get('API_PREFIX', '/api')


def load_test_data() -> dict:
    if not TEST_DATA_FILE.exists():
        raise FileNotFoundError(
            f'{TEST_DATA_FILE} tidak ada. Jalankan: python content_parser.py'
        )
    with open(TEST_DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


try:
    TEST_DATA = load_test_data()
except FileNotFoundError as e:
    logging.error(str(e))
    TEST_DATA = {'tokens': [], 'teacher_token': '', 'lessons': []}

STUDENT_TOKENS = [t for t in TEST_DATA.get('tokens', []) if t != TEST_DATA.get('teacher_token')]
TEACHER_TOKEN = TEST_DATA.get('teacher_token', '')
LESSON_SLUGS = [l['filename'].replace('.md', '') for l in TEST_DATA.get('lessons', [])]

if not STUDENT_TOKENS:
    logging.warning('test_data.json tidak punya token siswa — hanya teacher')


class StudentUser(HttpUser):
    """Siswa: login → baca lesson → track progress (random status)."""

    wait_time = between(1, 4)

    def on_start(self):
        self.token = random.choice(STUDENT_TOKENS) if STUDENT_TOKENS else ''
        if not self.token:
            return
        self.client.post(f'{API}/login', json={'token': self.token})

    @task(2)
    def validate_token(self):
        self.client.post(f'{API}/validate-token', json={'token': self.token})

    @task(3)
    def read_lesson(self):
        if not LESSON_SLUGS:
            return
        slug = random.choice(LESSON_SLUGS)
        self.client.get(f'/bab/dasar-pemrograman/{slug}', name='/bab/.../{slug}')

    @task(3)
    def track_progress(self):
        if not LESSON_SLUGS:
            return
        slug = random.choice(LESSON_SLUGS)
        status = random.choice(['completed', 'not_started', '3/4', '2/5'])
        self.client.post(
            f'{API}/track-progress',
            json={'token': self.token, 'lesson_name': slug, 'status': status},
        )


class TeacherUser(HttpUser):
    """Guru: login → report keseluruhan (beban baca berat di PG)."""

    wait_time = between(3, 8)

    def on_start(self):
        if TEACHER_TOKEN:
            self.client.post(f'{API}/login', json={'token': TEACHER_TOKEN})

    @task(1)
    def progress_report(self):
        if TEACHER_TOKEN:
            self.client.get(f'{API}/progress-report.json?token={TEACHER_TOKEN}')

    @task(1)
    def export_csv(self):
        if TEACHER_TOKEN:
            self.client.get(f'{API}/progress-report/export-csv?token={TEACHER_TOKEN}')
