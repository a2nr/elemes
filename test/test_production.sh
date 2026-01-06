#!/bin/bash

# Test script for LMS-C Production Environment

echo "Starting LMS-C Production Environment Tests..."

# Start the application
echo "Starting the application..."
cd ..
./start.sh
cd test

# Wait for the application to start
echo "Waiting for application to start..."
sleep 10

# Test 1: Check if the home page loads and displays lessons
echo "Test 1: Checking home page and lesson display..."
HOME_PAGE_CHECK=$(curl -s http://localhost:5000/ | grep -i "Available Lessons" | wc -l)
if [ $HOME_PAGE_CHECK -gt 0 ]; then
    echo "✓ Test 1 PASSED: Home page displays lessons correctly"
else
    echo "✗ Test 1 FAILED: Home page does not display lessons"
fi

# Test 2: Check if specific lesson pages load
echo "Test 2: Checking lesson page loading..."
LESSON_PAGE_CHECK=$(curl -s http://localhost:5000/lesson/welcome.md | grep -i "C Programming Learning System" | wc -l)
if [ $LESSON_PAGE_CHECK -gt 0 ]; then
    echo "✓ Test 2 PASSED: Lesson pages load correctly"
else
    echo "✗ Test 2 FAILED: Lesson pages do not load"
fi

# Test 3: Test the code compilation API
echo "Test 3: Testing code compilation API..."
COMPILATION_TEST=$(curl -s -X POST http://localhost:5000/compile \
  -H "Content-Type: application/json" \
  -d '{"code":"#include <stdio.h>\n\nint main() {\n    printf(\"Hello, World!\\n\");\n    return 0;\n}"}')

# Check if the response contains success: true and the expected output
if echo "$COMPILATION_TEST" | grep -q '"success":true' && echo "$COMPILATION_TEST" | grep -q "Hello, World!"; then
    echo "✓ Test 3 PASSED: Code compilation API works correctly"
else
    echo "✗ Test 3 FAILED: Code compilation API not working"
    echo "  Response: $COMPILATION_TEST"
fi

# Test 4: Test with a more complex C program
echo "Test 4: Testing complex code compilation..."
COMPLEX_CODE='{
  "code": "#include <stdio.h>\nint main() {\n    int i, sum = 0;\n    for (i = 1; i <= 5; i++) {\n        sum += i;\n    }\n    printf(\"Sum of 1 to 5 is: %d\\n\", sum);\n    return 0;\n}"
}'

COMPLEX_TEST=$(curl -s -X POST http://localhost:5000/compile \
  -H "Content-Type: application/json" \
  -d "$COMPLEX_CODE")

if echo "$COMPLEX_TEST" | grep -q '"success":true' && echo "$COMPLEX_TEST" | grep -q "Sum of 1 to 5"; then
    echo "✓ Test 4 PASSED: Complex code compilation works correctly"
else
    echo "✗ Test 4 FAILED: Complex code compilation not working"
    echo "  Response: $COMPLEX_TEST"
fi

# Test 5: Check if all expected lesson files are accessible
echo "Test 5: Checking lesson accessibility..."
LESSON_FILES=("welcome.md" "hello_world.md" "introduction_to_c.md" "arrays.md")
ALL_LESSONS_ACCESSIBLE=true

for lesson in "${LESSON_FILES[@]}"; do
    lesson_check=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5000/lesson/$lesson")
    if [ "$lesson_check" -ne 200 ]; then
        echo "✗ Lesson $lesson returned HTTP $lesson_check"
        ALL_LESSONS_ACCESSIBLE=false
    fi
done

if [ "$ALL_LESSONS_ACCESSIBLE" = true ]; then
    echo "✓ Test 5 PASSED: All test lessons are accessible"
else
    echo "✗ Test 5 FAILED: Some lessons are not accessible"
fi

# Test 6: Check for errors in container logs
echo "Test 6: Checking container logs for errors..."
LOG_ERRORS=$(podman logs elemes_lms-c_1 2>&1 | grep -i error | wc -l)
if [ $LOG_ERRORS -eq 0 ]; then
    echo "✓ Test 6 PASSED: No errors found in container logs"
else
    echo "✗ Test 6 FAILED: Errors found in container logs"
    podman logs elemes_lms-c_1 | grep -i error
fi

# Stop the application
echo "Stopping the application..."
cd ..
./stop.sh
cd test

echo "All tests completed!"