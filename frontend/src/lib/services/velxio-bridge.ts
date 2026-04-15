/**
 * PostMessage bridge for communicating with Velxio iframe (Arduino simulator).
 *
 * Elemes sends commands (load code, load circuit, get state) and Velxio
 * responds with events. Evaluation (serial, key_text, wiring) runs on the
 * Elemes side using data received from Velxio.
 */

import { checkKeyText } from './exercise';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface VelxioFile {
	name: string;
	content: string;
}

interface VelxioWire {
	start: { componentId: string; pinName: string };
	end: { componentId: string; pinName: string };
}

interface EvaluationExpected {
	key_text?: string;
	serial_output?: string;
	wiring?: [string, string][] | { wires: Array<{ start: { componentId: string; pinName: string }; end: { componentId: string; pinName: string } }> };
}

export interface EvaluationResult {
	pass: boolean;
	key_text?: boolean;
	serial?: boolean;
	wiring?: boolean;
	messages: string[];
	debug?: string[];
}

// ---------------------------------------------------------------------------
// Bridge
// ---------------------------------------------------------------------------

const READY_TIMEOUT_MS = 30_000;
const REQUEST_TIMEOUT_MS = 5_000;

export class VelxioBridge {
	private iframe: HTMLIFrameElement;
	private pending: Record<string, (data: any) => void> = {};
	private onReadyCallback: (() => void) | null = null;
	private boundOnMessage: (e: MessageEvent) => void;

	constructor(iframe: HTMLIFrameElement) {
		this.iframe = iframe;
		this.boundOnMessage = this.onMessage.bind(this);
		window.addEventListener('message', this.boundOnMessage);
	}

	// === Lifecycle ===

	/** Register a callback for when Velxio iframe reports ready. */
	onReady(callback: () => void) {
		this.onReadyCallback = callback;
	}

	/** Wait for velxio:ready with timeout. Returns false if timed out. */
	waitForReady(): Promise<boolean> {
		return new Promise((resolve) => {
			const timer = setTimeout(() => resolve(false), READY_TIMEOUT_MS);
			this.onReady(() => {
				clearTimeout(timer);
				resolve(true);
			});
		});
	}

	destroy() {
		window.removeEventListener('message', this.boundOnMessage);
		this.pending = {};
	}

	// === Commands (Elemes → Velxio) ===

	loadCode(files: VelxioFile[]) {
		this.send('elemes:load_code', { files });
	}

	loadCircuit(circuitJson: string) {
		try {
			const data = JSON.parse(circuitJson);
			this.send('elemes:load_circuit', data);
		} catch {
			console.error('VelxioBridge: invalid circuit JSON');
		}
	}

	setEmbedMode(options: { hideEditor?: boolean; hideAuth?: boolean; hideComponentPicker?: boolean; lockComponents?: boolean }) {
		this.send('elemes:set_embed_mode', options);
	}

	// === Evaluation ===

	async evaluate(expected: EvaluationExpected): Promise<EvaluationResult> {
		const result: EvaluationResult = { pass: false, messages: [] };
		const dbg: string[] = [];

		// 1. Key text check
		if (expected.key_text) {
			const resp = await this.request('elemes:get_source_code', 'velxio:source_code');
			if (resp) {
				const allCode = (resp.files as VelxioFile[]).map(f => f.content).join('\n');
				result.key_text = checkKeyText(allCode, expected.key_text);
				result.messages.push(result.key_text
					? '✅ Kata kunci ditemukan dalam kode'
					: '❌ Kata kunci yang dibutuhkan belum ada dalam kode');
				dbg.push(`[DBG key_text] keys="${expected.key_text.replace(/\n/g, ', ')}" → ${result.key_text}`);
			} else {
				result.key_text = false;
				result.messages.push('❌ Gagal mengambil source code dari simulator');
				dbg.push('[DBG key_text] resp=null (timeout)');
			}
		}

		// 2. Serial output
		if (expected.serial_output) {
			const resp = await this.request('elemes:get_serial_log', 'velxio:serial_log');
			if (resp) {
				const actualLog = resp.log as string;
				result.serial = this.matchSerial(actualLog, expected.serial_output);
				result.messages.push(result.serial
					? '✅ Serial output sesuai'
					: '❌ Serial output belum sesuai dengan yang diharapkan');
				dbg.push(`[DBG serial] actual(${actualLog.length} chars)="${actualLog.substring(0, 120).replace(/\n/g, '↵')}" → ${result.serial}`);
			} else {
				result.serial = false;
				result.messages.push('❌ Gagal mengambil serial log. Pastikan program sudah di-Run terlebih dahulu');
				dbg.push('[DBG serial] resp=null (timeout)');
			}
		}

		// 3. Wiring
		if (expected.wiring) {
			const resp = await this.request('elemes:get_wires', 'velxio:wires');
			if (resp) {
				const studentWires = resp.wires as VelxioWire[];
				const edges = studentWires.map(w =>
					`${w.start.componentId}:${w.start.pinName}↔${w.end.componentId}:${w.end.pinName}`
				);
				
				// Extract expected wires array from both formats
				let expectedWires: any[] = [];
				if (Array.isArray(expected.wiring)) {
					expectedWires = expected.wiring;
				} else if (expected.wiring.wires && Array.isArray(expected.wiring.wires)) {
					expectedWires = expected.wiring.wires;
				}
				
				result.wiring = this.matchWiring(studentWires, expectedWires);
				result.messages.push(result.wiring
					? '✅ Rangkaian wiring benar'
					: '❌ Wiring belum sesuai. Periksa kembali koneksi komponen');
				dbg.push(`[DBG wiring] ${studentWires.length} wires: ${edges.join(' | ')}`);
				dbg.push(`[DBG wiring] expected: ${expectedWires.map((w: any) => {
					if (Array.isArray(w) && w.length === 2) return w.join('↔');
					if (w.start && w.end) return `${w.start.componentId}:${w.start.pinName}↔${w.end.componentId}:${w.end.pinName}`;
					return JSON.stringify(w);
				}).join(' | ')}`);
				dbg.push(`[DBG wiring] → ${result.wiring}`);
			} else {
				result.wiring = false;
				result.messages.push('❌ Gagal mengambil data wiring dari simulator');
				dbg.push('[DBG wiring] resp=null (timeout)');
			}
		}

		// Overall pass: all checked criteria must be true
		const checks = [result.key_text, result.serial, result.wiring].filter(v => v !== undefined);
		result.pass = checks.length > 0 && checks.every(Boolean);

		// Store debug info separately
		result.debug = dbg;

		return result;
	}

	// === Internal ===

	private send(type: string, payload: Record<string, any> = {}) {
		this.iframe.contentWindow?.postMessage({ type, ...payload }, '*');
	}

	private request(sendType: string, expectType: string): Promise<any | null> {
		return new Promise((resolve) => {
			this.pending[expectType] = resolve;
			this.send(sendType);
			setTimeout(() => {
				if (this.pending[expectType]) {
					delete this.pending[expectType];
					resolve(null);
				}
			}, REQUEST_TIMEOUT_MS);
		});
	}

	private onMessage(event: MessageEvent) {
		const { type } = event.data || {};
		if (!type?.startsWith('velxio:')) return;

		if (type === 'velxio:ready' && this.onReadyCallback) {
			this.onReadyCallback();
		}

		if (this.pending[type]) {
			this.pending[type](event.data);
			delete this.pending[type];
		}
	}

	/** Subsequence match: expected lines must appear in order within actual. */
	private matchSerial(actual: string, expected: string): boolean {
		if (!expected.trim()) return true;
		if (!actual.trim()) return false;
		
		const actualLines = actual.split('\n').map(l => l.trim()).filter(l => l.length > 0);
		const expectedLines = expected.split('\n').map(l => l.trim()).filter(l => l.length > 0);
		
		let expectedIdx = 0;
		for (const actualLine of actualLines) {
			if (expectedIdx < expectedLines.length) {
				// Check if expected line is a substring of actual line (case-insensitive)
				if (actualLine.toLowerCase().includes(expectedLines[expectedIdx].toLowerCase())) {
					expectedIdx++;
				}
			}
			if (expectedIdx === expectedLines.length) return true;
		}
		return expectedIdx === expectedLines.length;
	}

	/**
	 * Net-based wiring check: groups pins into electrical nets using
	 * Union-Find (Disjoint Set Union), then compares net composition.
	 *
	 * This is robust against:
	 * - Node order swaps (A↔B vs B↔A)
	 * - Transitive connections (A-B-C vs A-C, B in middle)
	 * - Extra student wires (lenient - only missing connections fail)
	 */
	private matchWiring(studentWires: VelxioWire[], expectedPairs: [string, string][] | any[]): boolean {
		// Normalize power pin names (e.g., GND.2 → GND, VCC.1 → VCC)
		const normalizePin = (pin: string) => {
			return pin.replace(/^(GND|VCC|5V|3V3|3\.3V|POWER)\.\d+$/i, '$1');
		};

		const normPin = (pin: string) => {
			const [comp, name] = pin.includes(':') ? pin.split(':') : ['', pin];
			return `${comp}:${normalizePin(name)}`;
		};

		// Union-Find (DSU) implementation
		const parent = new Map<string, string>();
		const rank = new Map<string, string>();

		const find = (x: string): string => {
			if (!parent.has(x)) {
				parent.set(x, x);
				rank.set(x, x);
				return x;
			}
			// Path compression
			if (parent.get(x) !== x) {
				parent.set(x, find(parent.get(x)!));
			}
			return parent.get(x)!;
		};

		const union = (a: string, b: string) => {
			const rootA = find(a);
			const rootB = find(b);
			if (rootA === rootB) return;
			// Union by rank
			const rankA = rank.get(rootA) || '';
			const rankB = rank.get(rootB) || '';
			if (rankA < rankB) {
				parent.set(rootA, rootB);
			} else if (rankA > rankB) {
				parent.set(rootB, rootA);
			} else {
				parent.set(rootB, rootA);
				rank.set(rootA, rankA + '1');
			}
		};

		// Build student nets
		for (const wire of studentWires) {
			const start = normPin(`${wire.start.componentId}:${wire.start.pinName}`);
			const end = normPin(`${wire.end.componentId}:${wire.end.pinName}`);
			union(start, end);
		}

		// Collect all pins and group into nets for student
		const allStudentPins = new Set<string>();
		for (const wire of studentWires) {
			allStudentPins.add(normPin(`${wire.start.componentId}:${wire.start.pinName}`));
			allStudentPins.add(normPin(`${wire.end.componentId}:${wire.end.pinName}`));
		}

		const studentNets = new Map<string, Set<string>>();
		for (const pin of allStudentPins) {
			const root = find(pin);
			if (!studentNets.has(root)) {
				studentNets.set(root, new Set());
			}
			studentNets.get(root)!.add(pin);
		}

		// Build expected nets
		const expectedWires: Array<{ start: string; end: string }> = [];
		for (const expected of expectedPairs) {
			if (Array.isArray(expected) && expected.length === 2) {
				expectedWires.push({ start: normPin(expected[0]), end: normPin(expected[1]) });
			} else if (expected.start && expected.end) {
				expectedWires.push({
					start: normPin(`${expected.start.componentId}:${expected.start.pinName}`),
					end: normPin(`${expected.end.componentId}:${expected.end.pinName}`)
				});
			}
		}

		const expectedParent = new Map<string, string>();
		const expectedRank = new Map<string, string>();

		const expectedFind = (x: string): string => {
			if (!expectedParent.has(x)) {
				expectedParent.set(x, x);
				expectedRank.set(x, x);
				return x;
			}
			if (expectedParent.get(x) !== x) {
				expectedParent.set(x, expectedFind(expectedParent.get(x)!));
			}
			return expectedParent.get(x)!;
		};

		const expectedUnion = (a: string, b: string) => {
			const rootA = expectedFind(a);
			const rootB = expectedFind(b);
			if (rootA === rootB) return;
			const rankA = expectedRank.get(rootA) || '';
			const rankB = expectedRank.get(rootB) || '';
			if (rankA < rankB) {
				expectedParent.set(rootA, rootB);
			} else if (rankA > rankB) {
				expectedParent.set(rootB, rootA);
			} else {
				expectedParent.set(rootB, rootA);
				expectedRank.set(rootA, rankA + '1');
			}
		};

		for (const wire of expectedWires) {
			expectedUnion(wire.start, wire.end);
		}

		const allExpectedPins = new Set<string>();
		for (const wire of expectedWires) {
			allExpectedPins.add(wire.start);
			allExpectedPins.add(wire.end);
		}

		const expectedNets = new Map<string, Set<string>>();
		for (const pin of allExpectedPins) {
			const root = expectedFind(pin);
			if (!expectedNets.has(root)) {
				expectedNets.set(root, new Set());
			}
			expectedNets.get(root)!.add(pin);
		}

		// Compare: every expected net must have a matching student net
		// that contains ALL pins from the expected net
		for (const [, expectedNet] of expectedNets) {
			let found = false;
			for (const [, studentNet] of studentNets) {
				// Check if student net contains all pins from expected net
				let allPresent = true;
				for (const pin of expectedNet) {
					if (!studentNet.has(pin)) {
						allPresent = false;
						break;
					}
				}
				if (allPresent) {
					found = true;
					break;
				}
			}
			if (!found) {
				return false;
			}
		}

		return true;
	}
}
