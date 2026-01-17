"""
Load testing script for C Programming Learning Management System using Locust
"""

import os
import random
import csv
import glob
from locust import HttpUser, TaskSet, task, between
import json


def get_number_of_students():
    """
    Get the number of students from tokens_siswa.csv
    """
    tokens_file = '/mnt/locust/tokens_siswa.csv'
    num_students = 1  # Default to 1 if file doesn't exist or is empty

    if os.path.exists(tokens_file):
        with open(tokens_file, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';')
            # Count the number of data rows (excluding header)
            num_students = sum(1 for row in reader)

    return max(1, num_students)  # Ensure at least 1 student


class LMSCUserBehavior(TaskSet):
    """
    Define user behavior for the LMS-C application
    """

    def on_start(self):
        """
        Initialize user session with a token from tokens_siswa.csv
        """
        # Read all student data from tokens_siswa.csv
        tokens_file = '/mnt/locust/tokens_siswa.csv'
        all_students = []

        if os.path.exists(tokens_file):
            with open(tokens_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                all_students = list(reader)  # Convert to list to get all rows

        # Select a random student from the CSV
        if all_students:
            selected_student = random.choice(all_students)
            self.student_token = selected_student.get('token', f"STUDENT_TOKEN_{random.randint(1000, 9999)}")
            self.student_name = selected_student.get('nama_siswa', f"Student_{random.randint(1000, 9999)}")
        else:
            # Fallback if no students in CSV
            self.student_token = f"STUDENT_TOKEN_{random.randint(1000, 9999)}"
            self.student_name = f"Student_{random.randint(1000, 9999)}"

        # Register the student in the system
        register_payload = {
            "token": self.student_token,
            "student_name": self.student_name
        }

        # Try to register the student (this might fail if the token already exists, which is fine)
        try:
            self.client.post("/validate-token", json=register_payload)
        except:
            pass  # If validation fails, we'll continue anyway

        # Read lesson files from content directory
        content_dir = '/mnt/locust/content'  # Path relative to where locust runs in container
        self.lesson_files = []

        if os.path.exists(content_dir):
            lesson_paths = glob.glob(os.path.join(content_dir, "*.md"))
            self.lesson_files = [os.path.basename(path) for path in lesson_paths if os.path.isfile(path)]

        # No fallback to example_content since it won't be on the server
    
    @task(3)
    def view_homepage(self):
        """
        Task to view the homepage with lessons list
        """
        self.client.get("/")
    
    @task(2)
    def view_lesson(self):
        """
        Task to view a specific lesson
        """
        if self.lesson_files:
            # Randomly select a lesson to view from available lessons
            lesson = random.choice(self.lesson_files)
            self.client.get(f"/lesson/{lesson}?token={self.student_token}")
        else:
            # Visit homepage instead of falling back to example content
            self.client.get(f"/?token={self.student_token}")
    
    @task(1)
    def login_student(self):
        """
        Task to simulate student login
        """
        login_payload = {
            "token": self.student_token
        }
        
        response = self.client.post("/login", json=login_payload)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"Successfully logged in student: {data.get('student_name')}")
    
    @task(4)
    def compile_code(self):
        """
        Task to compile and run code (universal for any supported language)
        """
        # Determine the programming language from environment or default to 'c'
        programming_language = os.environ.get('DEFAULT_PROGRAMMING_LANGUAGE', 'c')

        # Get code from lesson content or use default samples
        code = self.get_code_from_lessons(programming_language)

        if not code:
            # Fallback to sample codes if no lesson content is available
            code = self.get_default_sample_code(programming_language)

        # Prepare payload for compilation
        compile_payload = {
            "code": code,
            "language": programming_language
        }

        # Send POST request to compile endpoint
        with self.client.post("/compile",
                             json=compile_payload,
                             catch_response=True) as response:
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    response.success()
                else:
                    response.failure(f"Compilation failed: {result.get('error', 'Unknown error')}")
            else:
                response.failure(f"HTTP {response.status_code}: Request failed")

    def get_code_from_lessons(self, language):
        """
        Extract code from lesson content using markers
        """
        if not self.lesson_files:
            return None

        # Select a random lesson to extract code from
        lesson_file = random.choice(self.lesson_files)
        lesson_path = f'/mnt/locust/content/{lesson_file}'

        if not os.path.exists(lesson_path):
            return None

        try:
            with open(lesson_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Look for INITIAL_CODE and SOLUTION_CODE sections
            initial_code = self.extract_code_section(content, '---INITIAL_CODE---', '---END_INITIAL_CODE---')
            solution_code = self.extract_code_section(content, '---SOLUTION_CODE---', '---END_SOLUTION_CODE---')

            # Choose randomly between initial and solution code if both exist
            available_codes = [code for code in [initial_code, solution_code] if code]

            if available_codes:
                return random.choice(available_codes)
        except Exception:
            pass  # If there's an error reading the file, return None

        return None

    def extract_code_section(self, content, start_marker, end_marker):
        """
        Extract code between start and end markers
        """
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            start_pos = start_idx + len(start_marker)
            extracted_code = content[start_pos:end_idx].strip()
            return extracted_code

        return None

    def get_default_sample_code(self, language):
        """
        Get default sample code based on the programming language
        """
        if language.lower() == 'c':
            sample_codes = [
                '''#include <stdio.h>

int main() {
    printf("Hello, World!\\n");
    return 0;
}''',
                '''#include <stdio.h>

int main() {
    int a = 5, b = 10;
    int sum = a + b;
    printf("Sum is: %d\\n", sum);
    return 0;
}''',
                '''#include <stdio.h>

int main() {
    int i;
    for(i = 0; i < 5; i++) {
        printf("Count: %d\\n", i);
    }
    return 0;
}'''
            ]
        elif language.lower() == 'python':
            sample_codes = [
                '''print("Hello, World!")''',
                '''
name = "Locust"
print(f"Hello, {name}!")''',
                '''
numbers = [1, 2, 3, 4, 5]
for num in numbers:
    print(f"Number: {num}")
'''
            ]
        else:
            # Default to C if language is not recognized
            sample_codes = [
                '''#include <stdio.h>

int main() {
    printf("Hello, World!\\n");
    return 0;
}'''
            ]

        return random.choice(sample_codes)
    
    @task(1)
    def validate_token(self):
        """
        Task to validate student token
        """
        validate_payload = {
            "token": self.student_token
        }
        
        self.client.post("/validate-token", json=validate_payload)
    
    @task(1)
    def track_progress(self):
        """
        Task to track student progress for a lesson
        """
        if self.lesson_files:
            # Select a random lesson from available lessons, removing .md extension for lesson_name
            lesson_file = random.choice(self.lesson_files)
            lesson_name = lesson_file.replace('.md', '')
        else:
            # Don't track progress if no lessons are available
            return

        progress_payload = {
            "token": self.student_token,
            "lesson_name": lesson_name,
            "status": "completed"
        }

        self.client.post("/track-progress", json=progress_payload)


class WebsiteUser(HttpUser):
    """
    Main user class for the LMS-C load test
    """
    tasks = [LMSCUserBehavior]

    # Wait time between tasks (1-3 seconds)
    wait_time = between(1, 3)

    def on_start(self):
        """
        Setup for each user when they start
        """
        # Perform initial homepage visit
        self.client.get("/")

    def on_stop(self):
        """
        Cleanup when user stops
        """
        # Logout the user
        try:
            self.client.post("/logout", json={})
        except:
            pass  # Ignore logout errors




# Additional task sets for more complex behaviors

class LessonNavigationTaskSet(TaskSet):
    """
    Task set focused on navigating through lessons
    """

    def on_start(self):
        """
        Initialize lesson navigation with available lessons
        """
        # Read lesson files from content directory
        content_dir = '/mnt/locust/content'  # Path relative to where locust runs in container
        self.lesson_files = []

        if os.path.exists(content_dir):
            lesson_paths = glob.glob(os.path.join(content_dir, "*.md"))
            self.lesson_files = [os.path.basename(path) for path in lesson_paths if os.path.isfile(path)]

        # No fallback to example_content since it won't be on the server

    @task(5)
    def browse_lessons(self):
        """
        Browse through different lessons
        """
        if self.lesson_files:
            for lesson in self.lesson_files:
                self.client.get(f"/lesson/{lesson}")
                self.wait()
        else:
            # No fallback since example_content won't be on the server
            # Just visit the homepage if no lessons are found
            self.client.get("/")
            self.wait()

    @task(2)
    def go_back_to_home(self):
        """
        Navigate back to home page
        """
        self.client.get("/")

    @task(1)
    def stop_browsing(self):
        """
        Stop browsing and potentially switch to another task set
        """
        self.interrupt()


class CompilationFocusedTaskSet(TaskSet):
    """
    Task set focused on code compilation activities
    """

    def on_start(self):
        """
        Initialize with lesson files for code extraction
        """
        # Read lesson files from content directory
        content_dir = '/mnt/locust/content'  # Path relative to where locust runs in container
        self.lesson_files = []

        if os.path.exists(content_dir):
            lesson_paths = glob.glob(os.path.join(content_dir, "*.md"))
            self.lesson_files = [os.path.basename(path) for path in lesson_paths if os.path.isfile(path)]

        # No fallback to example_content since it won't be on the server

    @task(10)
    def compile_different_codes(self):
        """
        Compile various programs based on the default language or from lesson content
        """
        # Determine the programming language from environment or default to 'c'
        programming_language = os.environ.get('DEFAULT_PROGRAMMING_LANGUAGE', 'c')

        # Get code from lesson content or use default samples
        code = self.get_code_from_lessons(programming_language)

        if not code:
            # Fallback to sample codes if no lesson content is available
            code = self.get_default_sample_code(programming_language)

        response = self.client.post("/compile", json={
            "code": code,
            "language": programming_language
        })

        if response.status_code == 200:
            result = response.json()
            if not result.get("success"):
                print(f"Compilation error: {result.get('error')}")

    def get_code_from_lessons(self, language):
        """
        Extract code from lesson content using markers
        """
        if not self.lesson_files:
            return None

        # Select a random lesson to extract code from
        lesson_file = random.choice(self.lesson_files)
        lesson_path = f'/mnt/locust/content/{lesson_file}'

        if not os.path.exists(lesson_path):
            return None

        try:
            with open(lesson_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Look for INITIAL_CODE and SOLUTION_CODE sections
            initial_code = self.extract_code_section(content, '---INITIAL_CODE---', '---END_INITIAL_CODE---')
            solution_code = self.extract_code_section(content, '---SOLUTION_CODE---', '---END_SOLUTION_CODE---')

            # Choose randomly between initial and solution code if both exist
            available_codes = [code for code in [initial_code, solution_code] if code]

            if available_codes:
                return random.choice(available_codes)
        except Exception:
            pass  # If there's an error reading the file, return None

        return None

    def extract_code_section(self, content, start_marker, end_marker):
        """
        Extract code between start and end markers
        """
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            start_pos = start_idx + len(start_marker)
            extracted_code = content[start_pos:end_idx].strip()
            return extracted_code

        return None

    def get_default_sample_code(self, language):
        """
        Get default sample code based on the programming language
        """
        if language.lower() == 'c':
            sample_codes = [
                '''#include <stdio.h>
int main() { printf("Simple Hello World\\n"); return 0; }''',
                '''#include <stdio.h>
int main() {
    int arr[] = {1, 2, 3, 4, 5};
    int i;
    for(i = 0; i < 5; i++) {
        printf("%d ", arr[i]);
    }
    printf("\\n");
    return 0;
}''',
                '''#include <stdio.h>
int factorial(int n) {
    if(n <= 1) return 1;
    return n * factorial(n-1);
}
int main() {
    int num = 5;
    printf("Factorial of %d is %d\\n", num, factorial(num));
    return 0;
}'''
            ]
        elif language.lower() == 'python':
            sample_codes = [
                '''print("Hello, World!")''',
                '''
name = "Locust"
print(f"Hello, {name}!")''',
                '''
numbers = [1, 2, 3, 4, 5]
for num in numbers:
    print(f"Number: {num}")
'''
            ]
        else:
            # Default to C if language is not recognized
            sample_codes = [
                '''#include <stdio.h>
int main() { printf("Simple Hello World\\n"); return 0; }'''
            ]

        return random.choice(sample_codes)


class AdvancedUser(HttpUser):
    """
    Advanced user that performs more complex behaviors
    """
    weight = 2  # Twice as likely to be chosen as WebsiteUser
    tasks = {LessonNavigationTaskSet: 2, CompilationFocusedTaskSet: 3, LMSCUserBehavior: 4}

    wait_time = between(0.5, 2)


class SessionBasedUser(HttpUser):
    """
    User that simulates a complete learning session with focused behavior
    """
    weight = 1
    tasks = [LMSCUserBehavior]

    wait_time = between(2, 5)

    def on_start(self):
        """
        Initialize a complete learning session
        """
        # Login at the beginning of the session
        tokens_file = '/mnt/locust/tokens_siswa.csv'
        all_students = []

        if os.path.exists(tokens_file):
            with open(tokens_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                all_students = list(reader)

        if all_students:
            selected_student = random.choice(all_students)
            self.student_token = selected_student.get('token', f"STUDENT_TOKEN_{random.randint(1000, 9999)}")
            self.student_name = selected_student.get('nama_siswa', f"Student_{random.randint(1000, 9999)}")
        else:
            self.student_token = f"STUDENT_TOKEN_{random.randint(1000, 9999)}"
            self.student_name = f"Student_{random.randint(1000, 9999)}"

        # Login the student
        login_payload = {
            "token": self.student_token
        }

        try:
            self.client.post("/login", json=login_payload)
        except:
            pass  # Continue even if login fails

        # Read lesson files
        content_dir = '/mnt/locust/content'
        self.lesson_files = []

        if os.path.exists(content_dir):
            lesson_paths = glob.glob(os.path.join(content_dir, "*.md"))
            self.lesson_files = [os.path.basename(path) for path in lesson_paths if os.path.isfile(path)]


class BehaviorAnalysisTaskSet(TaskSet):
    """
    Task set for analyzing user behavior patterns
    """

    def on_start(self):
        """
        Initialize with student data
        """
        tokens_file = '/mnt/locust/tokens_siswa.csv'
        all_students = []

        if os.path.exists(tokens_file):
            with open(tokens_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                all_students = list(reader)

        if all_students:
            selected_student = random.choice(all_students)
            self.student_token = selected_student.get('token', f"STUDENT_TOKEN_{random.randint(1000, 9999)}")
            self.student_name = selected_student.get('nama_siswa', f"Student_{random.randint(1000, 9999)}")
        else:
            self.student_token = f"STUDENT_TOKEN_{random.randint(1000, 9999)}"
            self.student_name = f"Student_{random.randint(1000, 9999)}"

        # Read lesson files
        content_dir = '/mnt/locust/content'
        self.lesson_files = []

        if os.path.exists(content_dir):
            lesson_paths = glob.glob(os.path.join(content_dir, "*.md"))
            self.lesson_files = [os.path.basename(path) for path in lesson_paths if os.path.isfile(path)]

    @task(3)
    def analyze_learning_pattern(self):
        """
        Simulate a learning pattern where a student goes through multiple lessons in sequence
        """
        if not self.lesson_files:
            return

        # Select a few lessons to go through in sequence
        selected_lessons = random.sample(self.lesson_files, min(3, len(self.lesson_files)))

        for lesson in selected_lessons:
            # Visit the lesson
            self.client.get(f"/lesson/{lesson}?token={self.student_token}")

            # Spend some time reading (simulate wait)
            self.wait()

            # Try to compile code from the lesson
            self.compile_code_from_lesson(lesson)

            # Track progress for the lesson
            lesson_name = lesson.replace('.md', '')
            progress_payload = {
                "token": self.student_token,
                "lesson_name": lesson_name,
                "status": "in_progress"
            }
            self.client.post("/track-progress", json=progress_payload)

            # Wait between activities
            self.wait()

        # Mark final lesson as completed
        if selected_lessons:
            final_lesson = selected_lessons[-1].replace('.md', '')
            progress_payload = {
                "token": self.student_token,
                "lesson_name": final_lesson,
                "status": "completed"
            }
            self.client.post("/track-progress", json=progress_payload)

    def compile_code_from_lesson(self, lesson_file):
        """
        Attempt to compile code from a specific lesson
        """
        lesson_path = f'/mnt/locust/content/{lesson_file}'

        if not os.path.exists(lesson_path):
            return

        try:
            with open(lesson_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Look for code sections in the lesson
            initial_code = self.extract_code_section(content, '---INITIAL_CODE---', '---END_INITIAL_CODE---')
            solution_code = self.extract_code_section(content, '---SOLUTION_CODE---', '---END_SOLUTION_CODE---')

            # Use available code for compilation
            code_to_compile = None
            if solution_code:
                code_to_compile = solution_code
            elif initial_code:
                code_to_compile = initial_code

            if code_to_compile:
                programming_language = os.environ.get('DEFAULT_PROGRAMMING_LANGUAGE', 'c')

                compile_payload = {
                    "code": code_to_compile,
                    "language": programming_language
                }

                response = self.client.post("/compile", json=compile_payload)

                if response.status_code == 200:
                    result = response.json()
                    if not result.get("success"):
                        print(f"Compilation error in lesson {lesson_file}: {result.get('error')}")
        except Exception as e:
            print(f"Error compiling code from lesson {lesson_file}: {str(e)}")

    def extract_code_section(self, content, start_marker, end_marker):
        """
        Extract code between start and end markers
        """
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            start_pos = start_idx + len(start_marker)
            extracted_code = content[start_pos:end_idx].strip()
            return extracted_code

        return None


class PowerUser(HttpUser):
    """
    Power user that exhibits intensive usage patterns
    """
    weight = 1
    tasks = {BehaviorAnalysisTaskSet: 3, CompilationFocusedTaskSet: 4, LMSCUserBehavior: 2}

    wait_time = between(0.2, 1.5)


class TeacherUser(HttpUser):
    """
    Teacher user that accesses the progress report feature
    """
    weight = 1
    tasks = [LMSCUserBehavior]

    wait_time = between(2, 5)

    def on_start(self):
        """
        Initialize teacher session
        """
        # Teachers don't need a specific token to view progress report
        # They can access the progress report page to see all students' progress
        pass

    @task(2)
    def view_progress_report(self):
        """
        Task to view the student progress report
        """
        # Access the progress report page
        response = self.client.get("/progress-report")

        # Check if the response is successful
        if response.status_code == 200:
            print("Successfully accessed progress report page")
        else:
            print(f"Failed to access progress report page: {response.status_code}")

    @task(1)
    def export_progress_csv(self):
        """
        Task to export the progress report as CSV
        """
        # Export the progress report as CSV
        response = self.client.get("/progress-report/export-csv")

        # Check if the response is successful
        if response.status_code == 200:
            print("Successfully exported progress report as CSV")
        else:
            print(f"Failed to export progress report as CSV: {response.status_code}")

    @task(1)
    def view_homepage_as_teacher(self):
        """
        Task for teacher to view homepage
        """
        # Teachers might also view the homepage
        self.client.get("/")


# Update the user_classes list to include the new TeacherUser
user_classes = [WebsiteUser, AdvancedUser, SessionBasedUser, PowerUser, TeacherUser]