---LESSON_INFO---
**Learning Objectives:**
- Understand basic syntax and structure of C programs
- Learn how to write your first C program
- Familiarize with the compilation process

**Prerequisites:**
- Basic understanding of programming concepts
- Familiarity with command line interface (optional)

---END_LESSON_INFO---
# Introduction to C Programming

C is a general-purpose, procedural computer programming language supporting structured programming, lexical variable scope, and recursion, with a static type system. By design, C provides constructs that map efficiently to typical machine instructions, which has made it one of the most widely used programming languages.


# Your First C Program Exercise

Write a C program that prints your name and your favorite programming language to the console.

**Requirements:**
- Use `printf` to output your name
- Include your favorite programming language in the output
- Make sure to include the standard input/output library
- The output should be in the format: "Hello, I am [Your Name] and my favorite programming language is [Language]"

**Example Output:**
```
Hello, I am John and my favorite programming language is C
```

Try writing your solution in the code editor below!

## History of C

C was originally developed at Bell Labs by Dennis Ritchie between 1972 and 1973. It was created to re-implement the Unix operating system, which was previously coded in assembly language.

## Basic Structure of a C Program

A basic C program consists of:
- Preprocessor directives
- Function definitions
- Variable declarations
- Comments
- Executable statements

Here's a simple example:

```c
#include <stdio.h>

int main() {
    printf("Hello, World!\n");
    return 0;
}
```

## Key Concepts

1. **Variables**: Storage locations with a name and data type
2. **Data Types**: Define what kind of value a variable can hold
3. **Functions**: Blocks of code that perform specific tasks
4. **Control Structures**: Direct the flow of program execution

---
## Common Data Types in C

| Type | Description | Example |
|------|-------------|---------|
| int | Integer values | `int age = 25;` |
| float | Floating-point numbers | `float price = 19.99;` |
| char | Single character | `char grade = 'A';` |
| double | Double precision float | `double pi = 3.14159;` |


---EXERCISE---

# Your First C Program Exercise

Write a C program that prints your name and your favorite programming language to the console.

**Requirements:**
- Use `printf` to output your name
- Include your favorite programming language in the output
- Make sure to include the standard input/output library
- The output should be in the format: "Hello, I am [Your Name] and my favorite programming language is [Language]"

**Expected Output:**
```
Hello, I am John and my favorite programming language is C
```

Try writing your solution in the code editor below!


---EXPECTED_OUTPUT---
Hello, I am John and my favorite programming language is C

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
    // Write your code here
    printf("Hello, I am John and my favorite programming language is C\n");
    return 0;
}
---END_SOLUTION_CODE---


-
