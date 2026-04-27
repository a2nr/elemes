import { checkKeyText, validateNodes } from '$services/exercise';
import type { LessonContent } from '$types/lesson';
import type { CircuitJSApi } from '$types/circuitjs';

export interface CircuitEvalResult {
	pass: boolean;
	output: string;
	error?: string;
}

export function evaluateCircuitSubmission(
	simApi: CircuitJSApi,
	circuitText: string,
	isHybrid: boolean,
	data: LessonContent,
	checkAllPassed: () => boolean
): CircuitEvalResult {
	const circuitExpected = (isHybrid && data.expected_circuit_output)
		? data.expected_circuit_output
		: data.expected_output;

	let expectedState: any = null;
	try {
		if (circuitExpected) expectedState = JSON.parse(circuitExpected);
	} catch {
		return { pass: false, output: '', error: "Format EXPECTED_OUTPUT tidak valid (Harus JSON)." };
	}

	if (!expectedState) {
		return { pass: true, output: "Tidak ada kriteria evaluasi yang ditetapkan." };
	}

	let { allPassed, messages } = expectedState.nodes
		? validateNodes(simApi, expectedState.nodes)
		: { allPassed: true, messages: [] as string[] };

	const circuitKeyText = (isHybrid && data.key_text_circuit) ? data.key_text_circuit : data.key_text;
	if (!checkKeyText(circuitText, circuitKeyText ?? '')) {
		allPassed = false;
		messages.push(`❌ Komponen wajib belum lengkap (lihat instruksi).`);
	}

	let finalOutput = messages.join('\n');
	
	if (allPassed && isHybrid) {
		finalOutput += '\n✅ Rangkaian benar!';
		if (!checkAllPassed()) {
			finalOutput += '\n⏳ Selesaikan juga tantangan kode untuk menyelesaikan pelajaran ini.';
		}
	}

	return { pass: allPassed, output: finalOutput };
}

export function processLanguageEvaluation(
	compileOutput: string,
	code: string,
	lang: 'c' | 'python',
	currentLanguage: string,
	cCode: string,
	pythonCode: string,
	data: LessonContent
): { isCorrect: boolean } {
	if (!data.expected_output) return { isCorrect: true };

	const currentCCode = (currentLanguage === 'c') ? code : cCode;
	const currentPythonCode = (currentLanguage === 'python') ? code : pythonCode;
	const mergedCode = currentCCode + '\n' + currentPythonCode;
	
	const isCorrect = compileOutput.trim() === data.expected_output.trim() && checkKeyText(mergedCode, data.key_text ?? '');
	return { isCorrect };
}
