from locust import HttpUser, TaskSet, task, between
import random
import json

class CProgrammingLMSUser(HttpUser):
    """
    Load testing for C Programming Learning Management System
    """
    wait_time = between(1, 3)
    
    def on_start(self):
        """
        Called when a user starts
        """
        # Get a list of available lessons to choose from
        self.lessons = []
        response = self.client.get("/")
        if response.status_code == 200:
            # In a real implementation, we would parse the response to get lesson URLs
            # For now, we'll use a predefined list of lesson paths
            self.lessons = [
                "introduction_to_c.md",
                "variables_and_data_types.md"
            ]
    
    @task(3)
    def view_home_page(self):
        """
        Task to view the home page
        """
        self.client.get("/")
    
    @task(5)
    def view_lesson(self):
        """
        Task to view a random lesson
        """
        if self.lessons:
            lesson = random.choice(self.lessons)
            self.client.get(f"/lesson/{lesson}")
    
    @task(2)
    def compile_c_code(self):
        """
        Task to compile C code using the API
        """
        # Sample C code for testing
        c_code = """
        #include <stdio.h>

        int main() {
            printf("Hello, World!\\n");
            return 0;
        }
        """
        
        response = self.client.post(
            "/compile",
            data={"code": c_code},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
    
    @task(1)
    def validate_token(self):
        """
        Task to validate a student token
        """
        # Use a random token for testing
        token = f"token_{random.randint(1000, 9999)}"
        
        response = self.client.post(
            "/validate-token",
            json={"token": token}
        )
    
    @task(1)
    def login_with_token(self):
        """
        Task to login with a student token
        """
        # Use a random token for testing
        token = f"token_{random.randint(1000, 9999)}"
        
        response = self.client.post(
            "/login",
            json={"token": token}
        )
    
    @task(1)
    def track_progress(self):
        """
        Task to track student progress
        """
        # Use a random token and lesson for testing
        token = f"token_{random.randint(1000, 9999)}"
        lesson_name = random.choice(["introduction_to_c", "variables_and_data_types"])
        
        response = self.client.post(
            "/track-progress",
            json={
                "token": token,
                "lesson_name": lesson_name,
                "status": "completed"
            }
        )