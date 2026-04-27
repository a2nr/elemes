import type { LessonContent } from '$types/lesson';

export interface VelxioEvalResult {
	pass: boolean;
	messages: string[];
	dbg: string[];
}

export function matchSerialSubsequence(actual: string, expected: string): boolean {
	if (!expected) return true;
	if (!actual) return false;
	
	const actualLines = actual.split('\n').map(l => l.trim()).filter(l => l.length > 0);
	const expectedLines = expected.split('\n').map(l => l.trim()).filter(l => l.length > 0);
	
	let expectedIdx = 0;
	for (const actualLine of actualLines) {
		if (expectedIdx < expectedLines.length) {
			if (actualLine.toLowerCase().includes(expectedLines[expectedIdx].toLowerCase())) {
				expectedIdx++;
			}
		}
		if (expectedIdx === expectedLines.length) return true;
	}
	return expectedIdx === expectedLines.length;
}

export function evaluateVelxioSubmission(
	sourceCode: string,
	serialLog: string,
	wireList: any[],
	data: LessonContent
): VelxioEvalResult {
	const messages: string[] = [];
	const dbg: string[] = [];
	let keyTextPass: boolean | undefined;
	let serialPass: boolean | undefined;
	let wiringPass: boolean | undefined;

	// 1. Key text
	if (data.key_text) {
		const keys = data.key_text.split('\n').map(k => k.trim()).filter(k => k.length > 0);
		keyTextPass = keys.every(key => sourceCode.includes(key));
		messages.push(keyTextPass
			? '✅ Kata kunci ditemukan dalam kode'
			: '❌ Kata kunci belum ada dalam kode');
		dbg.push(`[key_text] keys="${keys.join(', ')}" → ${keyTextPass}`);
	}

	// 2. Serial output
	if (data.expected_serial_output) {
		const actualLog = serialLog.trim();
		const expectedLog = data.expected_serial_output.trim();
		
		serialPass = matchSerialSubsequence(actualLog, expectedLog);
		
		messages.push(serialPass
			? '✅ Serial output sesuai'
			: '❌ Serial output belum sesuai');
		
		const preview = serialLog.substring(0, 150).replace(/\n/g, '↵');
		dbg.push(`[serial] actual(${serialLog.length}ch)="${preview}"`);
		dbg.push(`[serial] expected="${expectedLog.substring(0, 150).replace(/\n/g, '↵')}" → ${serialPass}`);
	}

	// 3. Wiring
	if (data.expected_wiring) {
		let expectedWires: any[] = [];
		try {
			const parsed = JSON.parse(data.expected_wiring);
			if (Array.isArray(parsed)) {
				expectedWires = parsed;
			} else if (parsed.wires && Array.isArray(parsed.wires)) {
				expectedWires = parsed.wires;
			}
		} catch {}

		const nonPolarizedTypes = new Set(['resistor']);

		const normalizePin = (pin: string) => {
			return pin.replace(/^(GND|VCC|5V|3V3|3\.3V|POWER)\.\d+$/i, '$1');
		};

		const norm = (a: string, b: string) => {
			const [compA, pinA] = a.split(':');
			const [compB, pinB] = b.split(':');
			const normA = `${compA}:${normalizePin(pinA || '')}`;
			const normB = `${compB}:${normalizePin(pinB || '')}`;
			const finalA = nonPolarizedTypes.has(compA) || compA.startsWith('resistor')
				? `${compA}:PIN` : normA;
			const finalB = nonPolarizedTypes.has(compB) || compB.startsWith('resistor')
				? `${compB}:PIN` : normB;
			return [finalA, finalB].sort().join('↔');
		};

		const studentEdges = new Set(
			wireList.map(w => norm(
				`${w.start.componentId}:${w.start.pinName}`,
				`${w.end.componentId}:${w.end.pinName}`
			))
		);

		wiringPass = expectedWires.every((expected: any) => {
			let edgeKey: string;
			if (Array.isArray(expected) && expected.length === 2) {
				edgeKey = norm(expected[0], expected[1]);
			} else if (expected.start && expected.end) {
				const startPin = `${expected.start.componentId}:${expected.start.pinName}`;
				const endPin = `${expected.end.componentId}:${expected.end.pinName}`;
				edgeKey = norm(startPin, endPin);
			} else {
				return false;
			}

			const exists = studentEdges.has(edgeKey);
			if (!exists) {
				dbg.push(`[wiring] MISSING: ${edgeKey}`);
			}
			return exists;
		});

		messages.push(wiringPass
			? '✅ Rangkaian wiring benar'
			: '❌ Wiring belum sesuai');

		const edgesStr = wireList.map(w =>
			`${w.start.componentId}:${w.start.pinName}↔${w.end.componentId}:${w.end.pinName}`
		);
		dbg.push(`[wiring] student (${wireList.length} wires): ${edgesStr.join(' | ') || '(kosong)'}`);
		dbg.push(`[wiring] expected (${expectedWires.length} connections): ${expectedWires.map((w: any) => {
			if (Array.isArray(w) && w.length === 2) return w.join('↔');
			if (w.start && w.end) return `${w.start.componentId}:${w.start.pinName}↔${w.end.componentId}:${w.end.pinName}`;
			return JSON.stringify(w);
		}).join(' | ')}`);
		dbg.push(`[wiring] result → ${wiringPass}`);
	}

	const checks = [keyTextPass, serialPass, wiringPass].filter(v => v !== undefined);
	const pass = checks.length > 0 && checks.every(Boolean);

	return { pass, messages, dbg };
}
