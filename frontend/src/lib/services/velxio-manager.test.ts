import { describe, it, expect, beforeEach } from 'vitest';
import { getVelxioState, resolveRestoredContent } from './velxio-manager';

class LocalStorageMock {
	private store: Record<string, string> = {};
	getItem(key: string) { return this.store[key] ?? null; }
	setItem(key: string, val: string) { this.store[key] = String(val); }
	removeItem(key: string) { delete this.store[key]; }
	clear() { this.store = {}; }
}
const mockStorage = new LocalStorageMock();
(global as any).localStorage = mockStorage;
(global as any).window = { localStorage: mockStorage };

describe('velxio-manager', () => {
	describe('getVelxioState', () => {
		it('should return null when iframe is null or contentWindow is missing', () => {
			expect(getVelxioState(null)).toBeNull();

			const mockIframeWithoutWin = {} as HTMLIFrameElement;
			expect(getVelxioState(mockIframeWithoutWin)).toBeNull();
		});

		it('should return null when Velxio Zustand stores are not attached to window', () => {
			const mockIframe = {
				contentWindow: {}
			} as HTMLIFrameElement;

			expect(getVelxioState(mockIframe)).toBeNull();
		});

		it('should extract code and circuit structure from Velxio stores correctly', () => {
			const mockEditorStore = {
				fileGroups: {
					'grp-1': [
						{ name: 'header.h', content: '#define LED 13' },
						{ name: 'sketch.ino', content: 'void setup() { pinMode(LED, OUTPUT); }\nvoid loop() {}' }
					]
				},
				files: []
			};

			const mockSimStore = {
				activeBoardId: 'board-1',
				boards: [
					{
						id: 'board-1',
						boardKind: 'arduino-uno',
						activeFileGroupId: 'grp-1'
					}
				],
				components: [
					{
						id: 'uno-1',
						metadataId: 'arduino-uno',
						x: 100.45,
						y: 200.89,
						properties: { rotation: 90, color: 'blue' }
					},
					{
						id: 'led-1',
						metadataId: 'led',
						x: 50,
						y: 80,
						properties: { color: 'red' }
					}
				],
				wires: [
					{
						start: { componentId: 'uno-1', pinName: '13' },
						end: { componentId: 'led-1', pinName: 'A' }
					},
					null
				]
			};

			const mockIframe = {
				contentWindow: {
					__VELXIO_EDITOR_STORE__: { getState: () => mockEditorStore },
					__VELXIO_SIMULATOR_STORE__: { getState: () => mockSimStore }
				}
			} as unknown as HTMLIFrameElement;

			const result = getVelxioState(mockIframe);
			expect(result).not.toBeNull();
			expect(result?.code).toBe('void setup() { pinMode(LED, OUTPUT); }\nvoid loop() {}');

			const parsedCircuit = JSON.parse(result!.circuit);
			expect(parsedCircuit.board).toBe('arduino:avr:uno');
			expect(parsedCircuit.components).toHaveLength(2);
			expect(parsedCircuit.components[0]).toEqual({
				id: 'uno-1',
				type: 'arduino-uno',
				x: 100.5,
				y: 200.9,
				rotation: 90,
				props: { rotation: 90, color: 'blue' }
			});
			expect(parsedCircuit.components[1]).toEqual({
				id: 'led-1',
				type: 'led',
				x: 50,
				y: 80,
				rotation: 0,
				props: { color: 'red' }
			});
			expect(parsedCircuit.wires).toHaveLength(1);
			expect(parsedCircuit.wires[0]).toEqual({
				start: { componentId: 'uno-1', pinName: '13' },
				end: { componentId: 'led-1', pinName: 'A' }
			});
		});

		it('should fallback to default files list and handle custom board FQBN', () => {
			const mockEditorStore = {
				fileGroups: {},
				files: [
					{ name: 'main.cpp', content: 'int main() { return 0; }' }
				]
			};

			const mockSimStore = {
				activeBoardId: 'custom-board',
				boards: [
					{
						id: 'custom-board',
						boardKind: 'custom:arch:myboard'
					}
				],
				components: [],
				wires: []
			};

			const mockIframe = {
				contentWindow: {
					__VELXIO_EDITOR_STORE__: { getState: () => mockEditorStore },
					__VELXIO_SIMULATOR_STORE__: { getState: () => mockSimStore }
				}
			} as unknown as HTMLIFrameElement;

			const result = getVelxioState(mockIframe);
			expect(result).not.toBeNull();
			expect(result?.code).toBe('int main() { return 0; }');

			const parsedCircuit = JSON.parse(result!.circuit);
			expect(parsedCircuit.board).toBe('custom:arch:myboard');
			expect(parsedCircuit.components).toEqual([]);
			expect(parsedCircuit.wires).toEqual([]);
		});
	});

	describe('resolveRestoredContent', () => {
		const KEY = 'test_arduino_code';
		const KEY_BASE = 'test_arduino_code_base';

		beforeEach(() => {
			localStorage.clear();
		});

		it('returns initial content when localStorage is empty', () => {
			const res = resolveRestoredContent(KEY, 'void setup() {}');
			expect(res.content).toBe('void setup() {}');
			expect(res.shouldRestore).toBe(false);
		});

		it('clears legacy draft (missing _base) and loads fresh server initial content', () => {
			localStorage.setItem(KEY, 'legacy code from old auto-save');
			const res = resolveRestoredContent(KEY, 'void setup() { Serial.begin(9600); }');
			expect(res.content).toBe('void setup() { Serial.begin(9600); }');
			expect(res.shouldRestore).toBe(false);
			expect(localStorage.getItem(KEY)).toBeNull();
		});

		it('clears draft when server initial content has changed (outdated baseline)', () => {
			localStorage.setItem(KEY, 'student modified code');
			localStorage.setItem(KEY_BASE, 'old initial code v1');

			const res = resolveRestoredContent(KEY, 'new initial code v2 published by teacher');
			expect(res.content).toBe('new initial code v2 published by teacher');
			expect(res.shouldRestore).toBe(false);
			expect(localStorage.getItem(KEY)).toBeNull();
			expect(localStorage.getItem(KEY_BASE)).toBeNull();
		});

		it('clears draft when saved code is identical to initial content (unmodified)', () => {
			localStorage.setItem(KEY, 'void setup() {}');
			localStorage.setItem(KEY_BASE, 'void setup() {}');

			const res = resolveRestoredContent(KEY, 'void setup() {}');
			expect(res.content).toBe('void setup() {}');
			expect(res.shouldRestore).toBe(false);
			expect(localStorage.getItem(KEY)).toBeNull();
		});

		it('restores student draft when baseline matches and code was modified', () => {
			localStorage.setItem(KEY, 'void setup() { pinMode(13, OUTPUT); }');
			localStorage.setItem(KEY_BASE, 'void setup() {}');

			const res = resolveRestoredContent(KEY, 'void setup() {}');
			expect(res.content).toBe('void setup() { pinMode(13, OUTPUT); }');
			expect(res.shouldRestore).toBe(true);
			expect(localStorage.getItem(KEY)).toBe('void setup() { pinMode(13, OUTPUT); }');
		});

		it('always returns initial content and cleans up storage when isTeacher is true', () => {
			localStorage.setItem(KEY, 'some draft code');
			localStorage.setItem(KEY_BASE, 'void setup() {}');

			const res = resolveRestoredContent(KEY, 'void setup() {}', true);
			expect(res.content).toBe('void setup() {}');
			expect(res.shouldRestore).toBe(false);
			expect(localStorage.getItem(KEY)).toBeNull();
			expect(localStorage.getItem(KEY_BASE)).toBeNull();
		});
	});
});
