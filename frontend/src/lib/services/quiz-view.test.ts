import { describe, it, expect } from 'vitest';
import { resolveQuizTabView, terminationReasonLabel, type QuizTabViewInput } from './quiz-view';

/** Baseline: kondisi "belum pernah kuis" — semua flag false. */
function input(overrides: Partial<QuizTabViewInput> = {}): QuizTabViewInput {
	return {
		isQuizMode: false,
		hasResult: false,
		quizAlreadyCompleted: false,
		quizResumable: false,
		hasStoredAttempt: false,
		questionCount: 0,
		...overrides
	};
}

describe('resolveQuizTabView', () => {
	it('sesi aktif menang atas SEMUA flag lain (regresi: resume → lembar jawaban)', () => {
		// Inilah bug yang ditemukan saat uji manual: setelah guru memberi resume
		// dan siswa klik "Lanjutkan Kuis", isQuizMode=true TAPI quizAlreadyCompleted
		// masih true (skor penalti lama dipertahankan). View harus 'active',
		// bukan 'summary'.
		const view = resolveQuizTabView(
			input({
				isQuizMode: true,
				hasResult: false,
				quizAlreadyCompleted: true,
				quizResumable: true,
				hasStoredAttempt: true,
				questionCount: 4
			})
		);
		expect(view).toBe('active');
	});

	it('sesi aktif tanpa soal → empty', () => {
		expect(resolveQuizTabView(input({ isQuizMode: true, questionCount: 0 }))).toBe('empty');
	});

	it('resume menang atas summary saat keduanya true (belum ada hasil sesi ini)', () => {
		const view = resolveQuizTabView(
			input({
				isQuizMode: false,
				quizResumable: true,
				hasStoredAttempt: true,
				quizAlreadyCompleted: true,
				questionCount: 4
			})
		);
		expect(view).toBe('resume');
	});

	it('hasil sesi ini MENANG atas panel resume (regresi: panel Lanjutkan muncul lagi setelah selesai)', () => {
		// Kejadian nyata: siswa menyelesaikan kuis resume, tapi sinyal
		// quizResumable/storedAttempt masih basi → panel "Lanjutkan Kuis"
		// muncul lagi dan menutupi ringkasan skor. hasResult harus menang.
		const view = resolveQuizTabView(
			input({
				isQuizMode: false,
				hasResult: true,
				quizResumable: true,
				hasStoredAttempt: true,
				quizAlreadyCompleted: true,
				questionCount: 5
			})
		);
		expect(view).toBe('summary');
	});

	it('resumable tetapi attempt tersimpan gagal dimuat → fallback summary', () => {
		const view = resolveQuizTabView(
			input({
				quizResumable: true,
				hasStoredAttempt: false,
				quizAlreadyCompleted: true
			})
		);
		expect(view).toBe('summary');
	});

	it('hasil sesi ini (result) → summary', () => {
		expect(resolveQuizTabView(input({ hasResult: true }))).toBe('summary');
	});

	it('sudah selesai (quizAlreadyCompleted) tanpa resume → summary', () => {
		expect(resolveQuizTabView(input({ quizAlreadyCompleted: true }))).toBe('summary');
	});

	it('belum pernah kuis → start', () => {
		expect(resolveQuizTabView(input())).toBe('start');
	});
});

describe('terminationReasonLabel', () => {
	it('memetakan kode audit ke label ramah pengguna', () => {
		expect(terminationReasonLabel('focus_lost')).toContain('fokus');
		expect(terminationReasonLabel('page_unload')).toContain('refresh');
		expect(terminationReasonLabel('spa_navigation')).toContain('halaman');
		expect(terminationReasonLabel('user_exit')).toContain('keluar');
		expect(terminationReasonLabel('completed')).toContain('selesai');
	});

	it('fallback: reason tak dikenal apa adanya, null/kosong → "dihentikan"', () => {
		expect(terminationReasonLabel('alasan_lain')).toBe('alasan_lain');
		expect(terminationReasonLabel(null)).toBe('dihentikan');
		expect(terminationReasonLabel(undefined)).toBe('dihentikan');
		expect(terminationReasonLabel('')).toBe('dihentikan');
	});
});
