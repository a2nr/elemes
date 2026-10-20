/**
 * Keputusan tampilan panel QuizTab (workspace kuis) sebagai fungsi MURNI.
 *
 * Dipisah dari komponen agar seluruh transisi view bisa diuji Vitest —
 * terutama transisi "resume → lembar jawaban aktif" yang rawan salah urutan
 * cabang (regresi: summary menang atas view aktif setelah guru memberi
 * izin resume, sehingga workspace tampak "tidak berubah").
 */

export type QuizTabView = 'resume' | 'summary' | 'start' | 'active' | 'empty';

export interface QuizTabViewInput {
	/** Sesi kuis sedang berjalan (soal aktif). */
	isQuizMode: boolean;
	/** `mgr.quizResult` sudah terisi (kuis baru difinalisasi di sesi ini). */
	hasResult: boolean;
	/** Gate one-attempt: status lesson terisi / attempt ada / stored attempt ada. */
	quizAlreadyCompleted: boolean;
	/** Guru memberi izin resume (data lesson / attempt audit). */
	quizResumable: boolean;
	/** Attempt tersimpan berhasil dimuat (punya attempt_id). */
	hasStoredAttempt: boolean;
	/** Jumlah soal pada sesi aktif. */
	questionCount: number;
}

/**
 * Prioritas: sesi aktif SELALU menang — agar setelah siswa menekan
 * "Lanjutkan Kuis" workspace langsung menampilkan lembar jawaban, meski
 * `quizAlreadyCompleted` masih true (skor penalti lama dipertahankan).
 *
 * Hasil sesi yang baru selesai (`hasResult`) menang atas panel resume: setelah
 * siswa menyelesaikan kuis resume, panel "Lanjutkan" tidak boleh muncul lagi
 * walau sinyal `quizResumable`/`storedAttempt` masih basi sampai reload.
 *
 * Urutan: active/empty → summary(hasil sesi ini) → resume → summary → start.
 */
export function resolveQuizTabView(input: QuizTabViewInput): QuizTabView {
	if (input.isQuizMode) {
		return input.questionCount > 0 ? 'active' : 'empty';
	}
	if (input.hasResult) return 'summary';
	if (input.quizResumable && input.hasStoredAttempt) return 'resume';
	if (input.quizAlreadyCompleted) return 'summary';
	return 'start';
}

/**
 * Label ramah pengguna untuk `termination_reason` (kode audit teknis →
 * bahasa yang dimengerti siswa). Fallback: reason apa adanya, atau "dihentikan".
 */
export function terminationReasonLabel(reason: string | null | undefined): string {
	switch (reason) {
		case 'focus_lost':
			return 'halaman kehilangan fokus (mis. berpindah tab/aplikasi)';
		case 'page_unload':
			return 'halaman di-refresh atau ditutup';
		case 'spa_navigation':
			return 'berpindah halaman';
		case 'user_exit':
			return 'keluar dari kuis';
		case 'completed':
			return 'kuis selesai';
		default:
			return reason ? reason : 'dihentikan';
	}
}
