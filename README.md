# C Programming Learning Management System

A web-based learning management system for C programming with interactive exercises and code compilation capabilities.

## Features

- View lessons written in Markdown format
- Interactive C code editor with compilation and execution
- Real-time feedback on code compilation and execution
- No database required - content stored as Markdown files
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
   podman run -p 5000:5000 -v $(pwd)/content:/app/content -v $(pwd)/static:/app/static -v $(pwd)/templates:/app/templates lms-c
   ```

## Adding New Lessons

To add new lessons:

1. Create a new Markdown file in the `content` directory with a `.md` extension
2. Structure your lesson with:
   - Lesson content at the top (using standard Markdown syntax)
   - A separator `---EXERCISE---` (optional)
   - Exercise content at the bottom (optional)

### Lesson Structure

**With Exercise:**
```markdown
# Lesson Title

Lesson content goes here...

## Section

More content...

---

EXERCISE---

# Exercise Title

Exercise instructions go here...

Try writing your solution in the code editor below!
```

**Without Exercise:**
```markdown
# Lesson Title

Lesson content goes here...

## Section

More content...
```

### Markdown Features Supported

- Headers: `#`, `##`, `###`
- Code blocks: Use triple backticks (```c for C code highlighting)
- Lists: `-` for unordered, `1.` for ordered
- Bold/italic: `**bold**`, `*italic*`
- Links: `[text](url)`
- Tables: Using standard Markdown table syntax

### Exercise Guidelines

- Exercises are optional - lessons can exist without them
- When an exercise is provided, it will appear above the code editor
- If no exercise is provided, a message will indicate that users can still practice with the code editor
- The code editor is always available for practice regardless of whether an exercise is defined

## How to Use

1. Access the application at `http://localhost:5000`
2. Browse available lessons
3. Click on a lesson to view content and exercises
4. Use the code editor to write C code
5. Click "Run Code" to compile and execute your code
6. View the output in the output panel

## Security Considerations

- The application runs C code in a containerized environment
- Timeouts are implemented to prevent infinite loops
- File system access is limited to the application directory

## Project Structure

- `app.py`: Main Flask application
- `content/`: Directory for lesson Markdown files
- `templates/`: HTML templates
- `static/`: CSS, JavaScript, and other static assets
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