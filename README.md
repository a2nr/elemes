# C Programming Learning Management System

A web-based learning management system for C programming with interactive exercises and code compilation capabilities.

## Features

- View lessons written in Markdown format
- Interactive C code editor with compilation and execution
- Real-time feedback on code compilation and execution
- No database required - content stored as Markdown files
- Student token-based progress tracking system
- No authentication required - ready to use out of the box
- Containerized with Podman for easy deployment

## Prerequisites

- Podman installed on your system
- Basic knowledge of Docker/Podman commands

## Getting Started

### Option 1: Using Podman Compose (Recommended)

1. Navigate to the project directory:
   ```bash
   cd lms-c
   ```

2. Build and start the container:
   ```bash
   podman-compose -f podman-compose.yml up --build
   ```

3. Access the application at `http://localhost:5000`

### Option 2: Using the Access Script

1. Make the access script executable:
   ```bash
   chmod +x access_container.sh
   ```

2. Run the access script:
   ```bash
   ./access_container.sh
   ```

   This will start the container and open a shell inside it. From there, you can run:
   ```bash
   python app.py
   ```

### Option 3: Direct Podman Commands

1. Build the image:
   ```bash
   podman build -t lms-c .
   ```

2. Run the container:
   ```bash
   podman run -p 5000:5000 -v ../content:/app/content -v ./static:/app/static -v ./templates:/app/templates -v ./tokens.csv:/app/tokens.csv lms-c
   ```

## Content Structure

The system uses Markdown files for content management. There are two main types of content files:

### Content Directory Location

The content directory is located at the parent directory level, outside of the `elemes/` directory. This allows for easy linking and sharing of content between different instances of the LMS.

### Home Page (`home.md`)

The home page serves as the main landing page and lesson directory. Here's the template structure:

```markdown
# Welcome to C Programming Learning System

This is a comprehensive learning platform designed to help you master the C programming language through interactive lessons and exercises.

## Learning Objectives

| Module | Objective | Skills Acquired |
|--------|-----------|-----------------|
| Introduction to C | Understand basic syntax and structure | Writing first C program |
| Variables & Data Types | Learn about different data types | Proper variable declaration |
| Control Structures | Master conditional statements and loops | Logic implementation |
| Functions | Create and use functions | Code organization |
| Arrays & Pointers | Work with complex data structures | Memory management |

## How to Use This System

1. **Browse Lessons**: Select from the available lessons on the left
2. **Read Content**: Study the lesson materials and examples
3. **Practice Coding**: Use the integrated code editor to write and test C code
4. **Complete Exercises**: Apply your knowledge to solve programming challenges
5. **Get Feedback**: See immediate results of your code execution

## Getting Started

Start with the "Introduction to C" lesson to begin your journey in C programming. Each lesson builds upon the previous one, so it's recommended to follow them in order.

Happy coding!

---Available_Lessons---

1. [Introduction to C Programming](lesson/introduction_to_c.md)
2. [Variables and Data Types in C](lesson/variables_and_data_types.md)
```

**Key Components of `home.md`:**
- Main title and welcome message
- Learning objectives table
- Usage instructions
- Getting started section
- `---Available_Lessons---` separator followed by a list of lessons in the format `[Lesson Title](lesson/filename.md)`

### Lesson Template

Each lesson file follows a specific structure to enable all system features. Here's the complete template:

```markdown
---LESSON_INFO---
**Learning Objectives:**
- Understand basic syntax and structure of C programs
- Learn how to write your first C program
- Familiarize with the compilation process

**Prerequisites:**
- Basic understanding of programming concepts
- Familiarity with command line interface (optional)

---END_LESSON_INFO---
# Lesson Title

Lesson content goes here...

## Section

More content...

---

## Common Data Types in C

| Type | Description | Example |
|------|-------------|---------|
| int | Integer values | `int age = 25;` |
| float | Floating-point numbers | `float price = 19.99;` |
| char | Single character | `char grade = 'A';` |
| double | Double precision float | `double pi = 3.14159;` |

---EXERCISE---

# Exercise Title

Exercise instructions go here...

**Requirements:**
- Requirement 1
- Requirement 2

**Expected Output:**
```
Expected output example
```

Try writing your solution in the code editor below!

---EXPECTED_OUTPUT---
Expected output text
---END_EXPECTED_OUTPUT---

---INITIAL_CODE---
#include <stdio.h>

int main() {
    // Write your code here
    printf("Hello, World!\\n");
    return 0;
}
---END_INITIAL_CODE---

---SOLUTION_CODE---
#include <stdio.h>

int main() {
    // Write your solution here
    printf("Solution output\\n");
    return 0;
}
---END_SOLUTION_CODE---
```

**Key Components of Lesson Files:**

1. **Lesson Information Block** (Optional):
   - `---LESSON_INFO---` and `---END_LESSON_INFO---` separators
   - Contains learning objectives and prerequisites
   - Appears in a special information card on the lesson page

2. **Main Content**:
   - Standard Markdown content with headers, text, tables, etc.
   - Supports all standard Markdown features including code blocks

3. **Exercise Block** (Optional):
   - `---EXERCISE---` separator
   - Exercise instructions and requirements
   - Appears above the code editor

4. **Expected Output Block** (Optional):
   - `---EXPECTED_OUTPUT---` and `---END_EXPECTED_OUTPUT---` separators
   - Defines the expected output for the exercise
   - When student code produces this output, they get a success message

5. **Initial Code Block** (Optional):
   - `---INITIAL_CODE---` and `---END_INITIAL_CODE---` separators
   - Provides starter code for the student
   - If not provided, defaults to a basic "Hello, World!" program

6. **Solution Code Block** (Optional):
   - `---SOLUTION_CODE---` and `---END_SOLUTION_CODE---` separators
   - Contains the correct solution
   - A "Show Solution" button appears when this is provided and the exercise is completed successfully

## Adding New Lessons

To add new lessons:

1. Create a new Markdown file in the `content` directory with a `.md` extension
2. Follow the lesson template structure above
3. Use standard Markdown syntax for content formatting
4. Add exercises with the `---EXERCISE---` separator if needed
5. Include expected output, initial code, and solution code as appropriate

### Complete Lesson Template

Here's a complete template with all optional sections for a new lesson:

```markdown
---LESSON_INFO---
**Learning Objectives:**
- Understand the purpose of this lesson
- Learn specific concepts or skills
- Apply knowledge to practical examples

**Prerequisites:**
- Knowledge from previous lessons
- Basic understanding of related concepts

---END_LESSON_INFO---
# Lesson Title

Lesson content goes here...

## Section

More content...

---

## Tables and Other Content

| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
| Data 4   | Data 5   | Data 6   |

---EXERCISE---

# Exercise Title

Exercise instructions go here...

**Requirements:**
- Requirement 1
- Requirement 2

**Expected Output:**
```
Expected output example
```

Try writing your solution in the code editor below!

---EXPECTED_OUTPUT---
Expected output text
---END_EXPECTED_OUTPUT---

---INITIAL_CODE---
#include <stdio.h>

int main() {
    // Write your code here
    printf("Hello, World!\\n");
    return 0;
}
---END_INITIAL_CODE---

---SOLUTION_CODE---
#include <stdio.h>

int main() {
    // Write your solution here
    printf("Solution output\\n");
    return 0;
}
---END_SOLUTION_CODE---
```

### Markdown Features Supported

- Headers: `#`, `##`, `###`
- Code blocks: Use triple backticks (```c for C code highlighting)
- Lists: `-` for unordered, `1.` for ordered
- Bold/italic: `**bold**`, `*italic*`
- Links: `[text](url)`
- Tables: Using standard Markdown table syntax
- Images: `![alt text](path/to/image)`
- Blockquotes: `> quoted text`

### Exercise Guidelines

- Exercises are optional - lessons can exist without them
- When an exercise is provided, it will appear above the code editor
- If no exercise is provided, a message will indicate that users can still practice with the code editor
- The code editor is always available for practice regardless of whether an exercise is defined
- Use `---EXPECTED_OUTPUT---` to provide automatic feedback when students complete exercises correctly
- Use `---INITIAL_CODE---` to provide starter code
- Use `---SOLUTION_CODE---` to provide a reference solution
- Use `---LESSON_INFO---` to provide learning objectives and prerequisites in a special information card

### Updating the Home Page

After creating new lessons, update the `../content/home.md` file to include links to your new lessons in the `---Available_Lessons---` section:

```markdown
---Available_Lessons---

1. [Lesson Title](lesson/filename.md)
```

### Content Organization

- Store all lesson files in the `../content/` directory (at the parent directory level)
- Use descriptive filenames with underscores instead of spaces (e.g., `variables_and_data_types.md`)
- Keep lesson files focused on a single topic or concept
- Use consistent formatting and structure across all lessons
- Include practical examples and exercises where appropriate

## Student Progress Tracking

The system includes a token-based progress tracking system:

1. A `tokens.csv` file is automatically generated based on the lessons in the content directory
2. Teachers manually add student tokens and names to this file
3. Students log in using their assigned token
4. Progress is automatically tracked when students complete exercises successfully
5. The system updates the CSV file with completion status for each lesson

To generate the tokens CSV file:
```bash
python generate_tokens.py
```

The CSV file format is: `token;nama_siswa;lesson1;lesson2;...`

## How to Use

1. Access the application at `http://localhost:5000`
2. Browse available lessons
3. Click on a lesson to view content and exercises
4. Use the code editor to write C code
5. Click "Run Code" to compile and execute your code
6. View the output in the output panel
7. For student tracking, use the token login field in the top navigation bar

## Using as a Submodule

This LMS can be used as a submodule in another repository. To set it up:

1. Add this repository as a submodule to your main project:
   ```bash
   git submodule add <repository-url> elemes
   ```

2. Create a content directory at the root level of your main project:
   ```bash
   mkdir content
   ```

3. Add your lesson files to the content directory

4. Run the LMS from the elemes directory:
   ```bash
   cd elemes
   podman-compose -f podman-compose.yml up --build
   ```

The content directory at the root level will be automatically mounted to the application container.

## Security Considerations

- The application runs C code in a containerized environment
- Timeouts are implemented to prevent infinite loops
- File system access is limited to the application directory
- Copy-paste functionality is disabled in the code editor to encourage manual coding

## Project Structure

- `app.py`: Main Flask application
- `../content/`: Directory for lesson Markdown files (at parent directory level)
- `templates/`: HTML templates
- `static/`: CSS, JavaScript, and other static assets
- `tokens.csv`: Student progress tracking file
- `generate_tokens.py`: Script to generate tokens CSV file
- `Dockerfile`: Container configuration
- `podman-compose.yml`: Podman Compose configuration
- `requirements.txt`: Python dependencies

## Development

To access the running container for development:

```bash
podman exec -it <container_name> /bin/bash
```

## Troubleshooting

- If you get permission errors, make sure your user has access to Podman
- If the application doesn't start, check that port 5000 is available
- If code compilation fails, verify that the gcc compiler is available in the container
- If progress tracking isn't working, ensure the tokens.csv file is properly formatted

## Stopping the Application

To stop the application:

### If running with Podman Compose:
```bash
# Stop the containers
podman-compose -f podman-compose.yml down

# Or if you want to stop and remove containers, networks, and volumes:
podman-compose -f podman-compose.yml down -v
```

### If running with direct Podman command:
```bash
# Find the container name or ID
podman ps

# Stop the container (replace <container_name> with actual name)
podman stop lms-c-container

# Remove the container after stopping (optional but recommended)
podman rm lms-c-container

# Or do both in one command:
podman stop lms-c-container && podman rm lms-c-container
```

### Using the access script:
If you're currently in the container shell opened via `access_container.sh`, you can:
1. Exit the container shell (type `exit`)
2. Then stop the container from outside:
   ```bash
   podman stop lms-c-container
   ```

### Troubleshooting: Port Already in Use

If you get an error about the port already being in use, it means the container wasn't properly stopped.
First, check what's using the port:
```bash
podman ps
```

If you see the `lms-c-container` still running, stop it:
```bash
podman stop lms-c-container && podman rm lms-c-container
```

Or stop all running containers:
```bash
podman stop $(podman ps -q)
```

Then you can run the application again on the desired port.

## API Endpoints

- `GET /` - Main page with all lessons
- `GET /lesson/<filename>` - View a specific lesson
- `POST /compile` - Compile and run C code (expects JSON with "code" field)
- `POST /login` - Validate student token
- `POST /validate-token` - Check if token is valid
- `POST /track-progress` - Update student progress
- `GET /static/<path>` - Serve static files

## Example API Usage

To compile and run C code via the API:

```bash
curl -X POST http://localhost:5000/compile \
  -H "Content-Type: application/json" \
  -d '{"code": "#include <stdio.h>\\n\\nint main() {\\n    printf(\\"Hello, World!\\\\n\\");\\n    return 0;\\n}"}'
```

Response:
```json
{
  "success": true,
  "output": "Hello, World!\n",
  "error": null
}
```

In case of compilation errors:
```json
{
  "success": false,
  "output": "error message...",
  "error": "Compilation failed"
}
```

## Load Testing with Locust

The system includes support for load testing using Locust to simulate multiple concurrent users accessing the LMS.

### Prerequisites for Load Testing

- Docker/Podman installed on the load testing machine
- Network access to the LMS server

### Running Load Tests

1. **Prepare the LMS Server**
   - Deploy the LMS container on the target server
   - Note the server IP address and port (default: http://<LMS_SERVER_IP>:5000)

2. **Configure Locust**
   - Update the `podman-compose.locust.yml` file with the correct LMS server IP address:
     ```yaml
     command: ["locust", "-f", "locustfile.py", "--host", "http://<LMS_SERVER_IP>:5000"]
     ```

3. **Run Locust Load Test**
   - On the load testing machine, navigate to the project directory
   - Build and start the Locust container:
     ```bash
     podman-compose -f test/podman-compose.locust.yml up --build
     ```
   - Access the Locust web interface at `http://localhost:8089`
   - Configure the number of users, spawn rate, and other parameters
   - Start the load test

4. **Alternative: Run Locust Directly**
   - Install Locust on the load testing machine:
     ```bash
     pip install -r locust/requirements.txt
     ```
   - Run Locust directly:
     ```bash
     cd locust
     locust -f locustfile.py --host http://<LMS_SERVER_IP>:5000
     ```

### Locust Test Scenarios

The included `locustfile.py` simulates the following user behaviors:
- Browsing the home page
- Viewing lessons
- Compiling C code
- Validating student tokens
- Logging in with tokens
- Tracking student progress

### Monitoring Performance

Monitor the LMS server's resource usage (CPU, memory, disk I/O) during load testing to identify potential bottlenecks. Pay attention to:
- Response times for API requests
- Compilation performance under load
- Database performance (if one is added in the future)
- Container resource limits
