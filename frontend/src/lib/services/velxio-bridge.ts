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
	wiring?: [string, string][];
}

export interface EvaluationResult {
	pass: boolean;
	key_text?: boolean;
	serial?: boolean;
	wiring?: boolean;
	messages: string[];
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

	setEmbedMode(options: { hideEditor?: boolean; hideAuth?: boolean; hideComponentPicker?: boolean }) {
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
				result.wiring = this.matchWiring(studentWires, expected.wiring);
				result.messages.push(result.wiring
					? '✅ Rangkaian wiring benar'
					: '❌ Wiring belum sesuai. Periksa kembali koneksi komponen');
				dbg.push(`[DBG wiring] ${studentWires.length} wires: ${edges.join(' | ')}`);
				dbg.push(`[DBG wiring] expected: ${expected.wiring.map(p => p.join('↔')).join(' | ')}`);
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

		// Append debug info to messages so it's visible in the output panel
		result.messages.push('', '── Debug ──', ...dbg);

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
		const actualLines = actual.trim().split('\n').map(l => l.trim());
		const expectedLines = expected.trim().split('\n').map(l => l.trim());
		let j = 0;
		for (const line of actualLines) {
			if (j < expectedLines.length && line === expectedLines[j]) j++;
			if (j === expectedLines.length) return true;
		}
		return j === expectedLines.length;
	}

	/** Lenient wiring check: all expected edges must exist in student wires. */
	private matchWiring(studentWires: VelxioWire[], expectedPairs: [string, string][]): boolean {
		// Normalize power pin names (e.g., GND.2 → GND, VCC.1 → VCC)
		const normalizePin = (pin: string) => pin.replace(/^(GND|VCC|5V|3V3|3\.3V)\.\d+$/i, '$1');
		
		const norm = (a: string, b: string) => {
			const normA = a.replace(/:(.+)$/, (_, pin) => ':' + normalizePin(pin));
			const normB = b.replace(/:(.+)$/, (_, pin) => ':' + normalizePin(pin));
			return [normA, normB].sort().join('↔');
		};
		const studentEdges = new Set(
			studentWires.map(w =>
				norm(
					`${w.start.componentId}:${w.start.pinName}`,
					`${w.end.componentId}:${w.end.pinName}`
				)
			)
		);
		return expectedPairs.every(([a, b]) => studentEdges.has(norm(a, b)));
	}
}
