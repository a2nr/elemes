/**
 * Kebijakan strict focus-loss untuk kuis (anti-cheat).
 *
 * Helper MURNI tanpa DOM/global browser agar keputusan event dapat diuji
 * di Vitest (environment node). Semua keputusan "apakah event ini mengakhiri
 * kuis" dipusatkan di sini — jangan menulis ulang logika di komponen.
 *
 * Policy strict: kehilangan fokus pertama saat kuis aktif langsung mengakhiri
 * kuis. Kembalinya fokus TIDAK pernah membatalkan termination.
 */

export type QuizTerminationReason =
	| 'focus_lost'
	| 'spa_navigation'
	| 'page_unload'
	| 'user_exit'
	| 'completed';

/** Nilai reason yang diizinkan — dipakai juga oleh kontrak backend. */
export const QUIZ_TERMINATION_REASONS: readonly QuizTerminationReason[] = [
	'focus_lost',
	'spa_navigation',
	'page_unload',
	'user_exit',
	'completed'
];

/**
 * Apakah sebuah event browser dianggap kehilangan fokus (strict mode)?
 *
 * - `visibilitychange` dengan state `hidden` → ya (switch tab, minimize,
 *   dan sebagian besar switch-app mobile).
 * - `blur` → ya (fallback desktop saat window kehilangan fokus tetapi
 *   visibility browser tidak berubah).
 * - Event apa pun setelah kuis terminated → tidak pernah (idempotent).
 * - `visibilitychange` kembali `visible` → tidak pernah.
 */
export function isFocusLossEvent(
	eventType: 'visibilitychange' | 'blur',
	visibilityState: DocumentVisibilityState,
	alreadyTerminated: boolean
): boolean {
	if (alreadyTerminated) return false;
	if (eventType === 'blur') return true;
	return visibilityState === 'hidden';
}

/**
 * Apakah pembahasan (review per-soal) boleh tampil di ringkasan setelah kuis
 * berakhir?
 *
 * Strict policy: kuis yang dihentikan karena `focus_lost` atau `page_unload`
 * TIDAK menampilkan pembahasan — siswa yang kehilangan fokus / me-refresh
 * halaman tidak mendapat bocoran jawaban. Alasan lain (`user_exit`,
 * `spa_navigation`, `completed`) tetap menampilkan pembahasan; `null`
 * (belum ada termination) → tampil.
 */
export function shouldShowQuizReview(reason: QuizTerminationReason | null): boolean {
	return reason !== 'focus_lost' && reason !== 'page_unload';
}

/**
 * UUID acak untuk `attempt_id` — korelasi/idempotency, BUKAN secret.
 *
 * Memakai `crypto.randomUUID()` bila tersedia; fallback menghasilkan string
 * berformat UUID berbasis waktu + random (valid untuk correlation &
 * idempotency, tidak digunakan sebagai credential).
 */
export function createAttemptId(): string {
	if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
		return crypto.randomUUID();
	}
	const rand = () =>
		Math.floor(Math.random() * 0x10000)
			.toString(16)
			.padStart(4, '0');
	const ts = Date.now().toString(16).padStart(12, '0');
	return `${ts.slice(0, 8)}-${ts.slice(8)}-${rand()}${rand()}-${rand()}${rand()}-${rand()}${rand()}${rand()}${rand()}`;
}
