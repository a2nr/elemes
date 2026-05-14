# 04. Lesson Evaluation

The LMS determines the type of lesson and how to evaluate it based on specific markers found in the Markdown content.

## Markdown Markers

| Mode | Marker | Evaluation Logic |
|------|--------|------------------|
| **C / Python** | `---INITIAL_CODE---` / `---INITIAL_PYTHON---` | Standard stdout matching against `---EXPECTED_OUTPUT---` and presence of `---KEY_TEXT---`. |
| **Circuit** | `---INITIAL_CIRCUIT---` | Node voltage matching against `---EXPECTED_CIRCUIT_OUTPUT---` and `---KEY_TEXT_CIRCUIT---`. |
| **Arduino (Velxio)** | `---INITIAL_CODE_ARDUINO---` | Serial output sequence matching, lenient graph wiring comparison, and `---KEY_TEXT---`. |
| **Quiz** | `---QUIZ_FLASHCARD---` | State completion tracking (all questions answered correctly). |
| **Slide** | `---slide-start---` | Tidak ada (hanya presentasi konten). |

## Evaluators (`lib/services/`)

The evaluation logic is isolated into specific service files:

### General & C/Python (`evaluators.ts`, `exercise.ts`)
- `export function checkKeyText(code: string, keyText: string): boolean`
  Checks if all lines in the `keyText` are present in the provided `code`.
- `export function processLanguageEvaluation(...)`
  Coordinates the compilation request and output verification for C and Python.

### Circuit Evaluation (`evaluators.ts`, `exercise.ts`)
- `export function evaluateCircuitSubmission(...)`
  Handles the flow of extracting the circuit state.
- `export function validateNodes(actualVoltages: Record<string, number>, expectedNodes: Record<string, NodeResult>): boolean`
  Validates if the actual node voltages match the expected voltages within a specified tolerance.

### Arduino/Velxio Evaluation (`velxio-evaluator.ts`, `velxio-bridge.ts`)
- `class VelxioBridge` (`velxio-bridge.ts`)
  Manages the `window.postMessage` protocol between the LMS and the Velxio iframe.
  - Commands: `elemes:load_code`, `elemes:load_circuit`, `elemes:get_source_code`, `elemes:get_serial_log`, `elemes:get_wires`.
  - Events: `velxio:ready`, `velxio:compile_result`.
- `export function evaluateVelxioSubmission(...)`
  Orchestrates the 3-part Arduino evaluation:
  1. **Key Text**: Checks the retrieved source code.
  2. **Serial Output**: Uses `matchSerialSubsequence(actual, expected)` to ensure expected log lines appear in the correct order.
  3. **Wiring**: Performs a lenient graph comparison (expected edges must exist; extra edges are allowed; ground pins are normalized).

### Flowchart Evaluation (`flowchart-evaluator.ts`)
- `export function evaluateFlowchartSubmission(...)`
  Parses flowchart JSON data and verifies structural correctness against the expected model.
