# Variables and Data Types in C

In C programming, variables are used to store data that can be manipulated during program execution. Each variable has a specific data type that determines the size and layout of the variable's memory, the range of values that can be stored, and the set of operations that can be applied to the variable.

## Declaring Variables

![variable](/assets/InitilizationofaVariable-660x330.png)

To use a variable in C, you must first declare it. The syntax for declaring a variable is:

```c
data_type variable_name;
```

For example:
```c
int age;
float height;
char initial;
```

You can also initialize variables at the time of declaration:

```c
int age = 25;
float height = 5.8;
char initial = 'J';
```

## Common Data Types

### Integer Types
- `int`: Used for integers (whole numbers)
- `short`: Short integer
- `long`: Long integer
- `long long`: Extended size integer

### Floating-Point Types
- `float`: Single precision floating-point
- `double`: Double precision floating-point
- `long double`: Extended precision floating-point

### Character Types
- `char`: Single character or small integer

### Void Type
- `void`: Represents the absence of type

## Variable Naming Rules

1. Variable names must begin with a letter or underscore
2. Names can contain letters, digits, and underscores
3. Names are case-sensitive
4. Names cannot be keywords (like `int`, `char`, etc.)
5. Names should be descriptive

## Constants

Constants are fixed values that your program cannot alter during execution. They can be:
- Integer constants: `100`, `-50`, `0`
- Floating-point constants: `3.14`, `-2.5`, `0.001`
- Character constants: `'a'`, `'X'`, `'3'`
- String literals: `"Hello, World!"`

---

---EXERCISE---

# Variables and Data Types Exercise

Write a C program that declares variables of different data types and prints their values.

**Requirements:**
1. Declare an integer variable called `quantity` and assign it the value 42
2. Declare a float variable called `price` and assign it the value 19.99
3. Declare a character variable called `grade` and assign it the value 'A'
4. Declare a double variable called `pi` and assign it the value 3.14159
5. Print all variables with appropriate labels

**Expected Output:**
```
Quantity: 42
Price: 19.990000
Grade: A
Pi: 3.141590
```

Remember to include the stdio.h header file and use the correct format specifiers in printf statements (%d for int, %f for float/double, %c for char).

Try writing your solution in the code editor below!


---EXPECTED_OUTPUT---

Quantity: 42
Price: 19.990000
Grade: A
Pi: 3.141590
