import { describe, it, expect } from 'vitest';
import { getVelxioState } from './velxio-manager';

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
});
