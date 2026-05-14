# 03. Frontend (SvelteKit)

The frontend is built using SvelteKit and Vite. It utilizes Svelte 5 for its reactivity model.

## Framework & State Management

The frontend uses two main state management patterns:
1.  **Svelte 5 Runes (`$state`, `$derived`, `$effect`)**: Used extensively in `.svelte` and `.svelte.ts` files. For instance, the lesson view uses `lessonState.svelte.ts` to manage all reactive data (active tabs, compilation status) outside of the UI components, moving away from a "God Component" architecture.
2.  **Writable Stores**: Used in standard `.ts` files (e.g., `lib/stores/auth.ts`, `lib/stores/theme.ts`) where Runes are not processed by the Svelte compiler.

## API Services (`lib/services/api.ts`)

This module provides wrappers for all backend calls. In production, SvelteKit uses `hooks.server.ts` to proxy requests starting with `/api/` to the Flask backend.

- `export function login(token: string, customFetch = fetch)`
- `export function logout(customFetch = fetch)`
- `export function validateToken(token: string, customFetch = fetch)`
- `export function getLessons(customFetch = fetch)`
- `export function getLesson(slug: string, customFetch = fetch, token = '')`
- `export function getKeyText(filename: string, customFetch = fetch)`
- `export function compileCode(req: CompileRequest, customFetch = fetch)`
- `export function trackProgress(lessonName: string, status: string = 'completed', customFetch = fetch)`
- `export function resetProgress(lessonName: string, customFetch = fetch)`

## Key Components

- **`LessonWorkspace.svelte`**: The main presentational component for the interactive lesson area. It wraps the editor, output panels, and tab switchers.
- **`CodeEditor.svelte`**: Wraps CodeMirror 6. It is lazy-loaded to reduce the initial bundle size and provides syntax highlighting for C and Python. It also implements strict anti-paste measures.
- **`VelxioIframe.svelte`**: Isolates the initialization of the `VelxioBridge`, the `postMessage` logic, and auto-save capabilities specific to the Arduino simulator.
- **`CircuitEditor.svelte`**: Wraps the Falstad CircuitJS simulator (a GWT-compiled app) inside an iframe. It mounts a transparent `CrosshairOverlay.svelte` on touch devices to enable precise interactions by translating touch events to synthetic mouse events.

## Security & Anti Copy-Paste

To prevent students from copying lesson text or pasting external code:
1.  **`lib/actions/noSelect.ts`**: A Svelte action that applies CSS (`user-select: none`) and attaches DOM event listeners (`onselectstart`, `oncopy`, `oncontextmenu` calling `preventDefault()`) to the lesson content.
2.  **Code Editor Defenses**: `CodeEditor.svelte` implements multiple layers:
    - DOM handlers for `paste`, `drop`, and `beforeinput`.
    - CodeMirror transaction filters to block `input.paste` and heuristics (e.g., blocking inserts > 20 characters or > 2 lines).
    - Clipboard API overriding when available.
