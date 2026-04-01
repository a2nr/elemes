/**
 * Pure helper functions for exercise evaluation.
 */

import type { CircuitJSApi } from '$types/circuitjs';

/** Check if code contains all required key_text keywords (one per line). */
export function checkKeyText(code: string, keyText: string): boolean {
	if (!keyText.trim()) return true;
	const keys = keyText.split('\n').map(k => k.trim()).filter(k => k.length > 0);
	return keys.every(key => code.includes(key));
}

export interface NodeResult {
	passed: boolean;
	message: string;
}

/** Validate circuit node voltages against expected state. */
export function validateNodes(
	simApi: CircuitJSApi,
	nodes: Record<string, { voltage: number; tolerance?: number }>
): { allPassed: boolean; messages: string[] } {
	let allPassed = true;
	const messages: string[] = [];

	for (const [nodeName, criteria] of Object.entries(nodes)) {
		const actualV = simApi.getNodeVoltage(nodeName);
		if (actualV === undefined || actualV === null) {
			allPassed = false;
			messages.push(`❌ Node '${nodeName}' tidak ditemukan.`);
			continue;
		}
		const tol = criteria.tolerance || 0.1;
		if (Math.abs(actualV - criteria.voltage) <= tol) {
			messages.push(`✅ Node '${nodeName}': Tegangan ${actualV.toFixed(2)}V (Sesuai)`);
		} else {
			allPassed = false;
			messages.push(`❌ Node '${nodeName}': Tegangan ${actualV.toFixed(2)}V (Harusnya ~${criteria.voltage}V)`);
		}
	}

	return { allPassed, messages };
}
