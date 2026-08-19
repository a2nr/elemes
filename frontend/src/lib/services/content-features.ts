import type { QuizQuestion } from '$types/quiz';

export type ContentFeatureId =
	| 'mcq'
	| 'mcq-diagnostik'
	| 'flashcard'
	| 'has-image'
	| 'has-explanation';

export interface ContentFeature {
	id: ContentFeatureId;
	label: string;
	/** 'auto' = bisa diverifikasi otomatis dari event/state LessonManager.
	 *  'manual' = guru konfirmasi sendiri secara visual. */
	verification: 'auto' | 'manual';
	checklistLabel: string;
}

const FEATURE_DEFINITIONS: Record<ContentFeatureId, Omit<ContentFeature, 'id'>> = {
	mcq: {
		label: 'Pilihan Ganda (evaluasi)',
		verification: 'manual',
		checklistLabel: 'Opsi MCQ tampil 2 kolom & bisa dipilih'
	},
	'mcq-diagnostik': {
		label: 'Pilihan Ganda (diagnostik)',
		verification: 'manual',
		checklistLabel: 'Soal diagnostik tidak masuk skor resmi (cek statusString)'
	},
	flashcard: {
		label: 'Flashcard',
		verification: 'auto',
		checklistLabel: 'Tombol "Sudah Mengerti" / "Tidak Mengerti" tersimpan (understood)'
	},
	'has-image': {
		label: 'Gambar soal',
		verification: 'manual',
		checklistLabel: 'Gambar soal tampil dengan benar'
	},
	'has-explanation': {
		label: 'Pembahasan',
		verification: 'manual',
		checklistLabel: 'Pembahasan muncul di ringkasan setelah kuis selesai (bukan saat mengerjakan)'
	}
};

// Anti-cheat (focus_lost/page_unload) SENGAJA TIDAK masuk feature-detection —
// itu policy global yang selalu aktif untuk SEMUA kuis (lihat quiz-integrity.ts),
// bukan sesuatu yang "dipakai" per-konten. Checklist item untuk anti-cheat
// selalu ditampilkan terpisah, tidak bergantung deteksi konten (lihat CHECKLIST-02).

export function detectContentFeatures(questions: QuizQuestion[] | undefined): ContentFeature[] {
	if (!questions?.length) return [];
	const ids = new Set<ContentFeatureId>();
	for (const q of questions) {
		if (q.type === 'mcq') {
			ids.add(q.category === 'diagnostik' ? 'mcq-diagnostik' : 'mcq');
		} else if (q.type === 'flashcard') {
			ids.add('flashcard');
		}
		if (q.image) ids.add('has-image');
		if (q.explanation) ids.add('has-explanation');
	}
	return Array.from(ids).map((id) => ({ id, ...FEATURE_DEFINITIONS[id] }));
}
