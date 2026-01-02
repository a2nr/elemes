"""
Load testing script for C Programming Learning Management System
Using Locust to simulate 50+ concurrent students accessing the application
"""

from locust import HttpUser, TaskSet, task, between
import random
import json


class StudentBehavior(TaskSet):
    """
    Define the behavior of a student using the LMS
    """
    
    def on_start(self):
        """Initialize the user session - potentially with a valid token"""
        self.token = None
        self.student_name = None
        self.current_lesson = None
        self.lessons = []
        
        # Get available lessons
        response = self.client.get("/")
        if response.status_code == 200:
            # In a real scenario, we would parse the response to get lesson names
            # For now, we'll use a predefined list of possible lessons
            self.lessons = [
                "variables.md", "loops.md", "functions.md", 
                "arrays.md", "pointers.md", "structures.md"
            ]
    
    @task(3)
    def view_homepage(self):
        """View the main page with all lessons"""
        self.client.get("/")
    
    @task(4)
    def view_lesson(self):
        """View a random lesson page"""
        if self.lessons:
            lesson = random.choice(self.lessons)
            self.client.get(f"/lesson/{lesson}")
    
    @task(2)
    def compile_code(self):
        """Submit code for compilation (simulating exercise completion)"""
        sample_codes = [
            '''#include <stdio.h>
int main() {
    printf("Hello, World!\\n");
    return 0;
}''',
            '''#include <stdio.h>
int main() {
    int a = 5, b = 10;
    printf("Sum: %d\\n", a + b);
    return 0;
}''',
            '''#include <stdio.h>
int main() {
    for(int i = 0; i < 5; i++) {
        printf("Count: %d\\n", i);
    }
    return 0;
}'''
        ]
        
        code = random.choice(sample_codes)
        
        response = self.client.post(
            "/compile",
            json={"code": code},
            headers={"Content-Type": "application/json"}
        )
    
    @task(1)
    def login(self):
        """Attempt to log in with a token"""
        # Using a random token for testing - in a real scenario, 
        # we would use valid tokens from a pool
        tokens_pool = [
            "STUDENT001", "STUDENT002", "STUDENT003", "STUDENT004", "STUDENT005",
            "STUDENT006", "STUDENT007", "STUDENT008", "STUDENT009", "STUDENT010"
        ]
        
        token = random.choice(tokens_pool)
        
        response = self.client.post(
            "/login",
            json={"token": token},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("success"):
                    self.token = token
                    self.student_name = data.get("student_name")
            except json.JSONDecodeError:
                pass  # Handle non-JSON responses
    
    @task(1)
    def validate_token(self):
        """Validate a token"""
        tokens_pool = [
            "STUDENT001", "STUDENT002", "STUDENT003", "STUDENT004", "STUDENT005",
            "STUDENT006", "STUDENT007", "STUDENT008", "STUDENT009", "STUDENT010"
        ]
        
        token = random.choice(tokens_pool)
        
        response = self.client.post(
            "/validate-token",
            json={"token": token},
            headers={"Content-Type": "application/json"}
        )
    
    @task(1)
    def track_progress(self):
        """Track progress for a lesson (only if logged in)"""
        if self.token and self.lessons:
            lesson_name = random.choice(self.lessons).replace('.md', '')
            
            response = self.client.post(
                "/track-progress",
                json={
                    "token": self.token,
                    "lesson_name": lesson_name,
                    "status": "completed"
                },
                headers={"Content-Type": "application/json"}
            )


class WebsiteUser(HttpUser):
    """
    Main user class for the load test
    """
    tasks = [StudentBehavior]
    wait_time = between(1, 5)  # Wait between 1-5 seconds between requests
    
    # Host where the application is running
    host = "http://localhost:5000"