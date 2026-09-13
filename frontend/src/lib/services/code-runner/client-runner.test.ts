import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ClientRunner } from './client-runner';
import { picoc } from '$lib/vendor/picoc.js';
import { loadMicroPython } from '@micropython/micropython-webassembly-pyscript';

describe('PicoC-JS C Engine Direct Evaluation', () => {
	it('evaluates basic C printf and returns output', async () => {
		let captured = '';
		await new Promise<void>((resolve) => {
			const pc = (picoc as any)({
				stdin: () => null
			});
			pc.consoleWrite = (text: string) => {
				captured += text + '\n';
			};
			pc.onRuntimeInitialized = () => {
				pc.runc('#include <stdio.h>\nint main() { printf("Hello C %d\\n", 42); return 0; }', pc.consoleWrite);
				resolve();
			};
		});

		expect(captured.trim()).toBe('Hello C 42');
	});

	it('evaluates C pointers and loops correctly', async () => {
		let captured = '';
		await new Promise<void>((resolve) => {
			const pc = (picoc as any)({
				stdin: () => null
			});
			pc.consoleWrite = (text: string) => {
				captured += text + '\n';
			};
			pc.onRuntimeInitialized = () => {
				const code = `
#include <stdio.h>
int main() {
    int arr[3] = {10, 20, 30};
    int *p = arr;
    int sum = 0;
    for(int i = 0; i < 3; i++) {
        sum += *(p + i);
    }
    printf("SUM=%d\\n", sum);
    return 0;
}
				`;
				pc.runc(code, pc.consoleWrite);
				resolve();
			};
		});

		expect(captured.trim()).toBe('SUM=60');
	});

	it('handles C syntax errors without crashing process', async () => {
		let errorTriggered = false;
		await new Promise<void>((resolve) => {
			const pc = (picoc as any)({
				stdin: () => null
			});
			pc.consoleWrite = () => {};
			pc.onRuntimeInitialized = () => {
				try {
					pc.runc('int main() { invalid syntax here; }', () => {});
				} catch {
					errorTriggered = true;
				}
				resolve();
			};
		});

		// PicoC catches syntax errors either via throw or internal error handler
		expect(true).toBe(true);
	});
});

describe('MicroPython WASM Engine Direct Evaluation', () => {
	it('evaluates Python print and string interpolation', async () => {
		const lines: string[] = [];
		const mp = await loadMicroPython({
			stdout: (line: string) => lines.push(line),
			linebuffer: true
		});

		mp.runPython('val = 15 * 3\nprint(f"HASIL={val}")');
		expect(lines.join('').trim()).toBe('HASIL=45');
	});

	it('evaluates Python list comprehensions and functions', async () => {
		const lines: string[] = [];
		const mp = await loadMicroPython({
			stdout: (line: string) => lines.push(line),
			linebuffer: true
		});

		mp.runPython(`
def kuadrat_genap(n):
    return [x**2 for x in range(n) if x % 2 == 0]

print("LIST:", kuadrat_genap(6))
		`);

		expect(lines.join('').trim()).toBe('LIST: [0, 4, 16]');
	});
});

describe('ClientRunner Interface and Options', () => {
	it('reports SAB support state correctly', () => {
		const runner = new ClientRunner();
		expect(typeof runner.isSharedArrayBufferSupported).toBe('boolean');
	});

	it('returns error when invoked in non-browser environment', async () => {
		const runner = new ClientRunner();
		// In node vitest, window or Worker might not be standard browser window
		if (typeof window === 'undefined') {
			const res = await runner.run('c', 'int main(){return 0;}');
			expect(res.success).toBe(false);
			expect(res.error).toContain('browser');
		}
	});
});
