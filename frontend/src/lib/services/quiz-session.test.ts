import { describe, it, expect } from 'vitest';
import {
  createQuizSession,
  calculateQuizResult,
  restoreQuizSession,
  firstUnansweredIndex,
  answerQuestion,
  questionMaxPoints,
  QUIZ_PASS_THRESHOLD,
} from './quiz-session';
import type { QuizQuestion, QuizOption } from '../types/quiz';

function opts(id: string, weights: Array<number | null>, correctMax = true): QuizOption[] {
  // Opsi dari daftar bobot; opsi bobot tertinggi = kunci (weighted), atau
  // weight 1 utk biner. correctMax=false membalik kunci ke opsi pertama.
  const maxW = weights.reduce<number>((m, w) => Math.max(m, w ?? 0), 0);
  return weights.map((w, i) => ({
    id: `${id}-o-${i}`,
    text: `opt ${i}`,
    weight: w ?? 0,
    is_correct: correctMax ? (w ?? 0) === maxW && maxW > 0 : i === 0,
  }));
}

function mcq(id: string, nOpts: number, correctIdx = 0): QuizQuestion {
  const options = Array.from({ length: nOpts }, (_, i) => ({
    id: `${id}-o-${i}`,
    text: `opt ${i}`,
    weight: i === correctIdx ? 1 : 0,
    is_correct: i === correctIdx,
  }));
  return {
    id,
    type: 'mcq',
    quiz_type: 'mcq',
    question: `Q ${id}`,
    options,
    category: 'evaluasi',
    explanation: '',
  } as QuizQuestion;
}

function weighted(id: string, weights: Array<number | null>): QuizQuestion {
  return {
    id,
    type: 'mcq',
    quiz_type: 'weighted',
    question: `W ${id}`,
    options: opts(id, weights),
    category: 'evaluasi',
    explanation: '',
  } as QuizQuestion;
}

describe('createQuizSession shuffle integrity', () => {
  it('opsi tetap lengkap & konsisten setelah shuffle (rng acak)', () => {
    const source = [mcq('q-0', 4), mcq('q-1', 3), mcq('q-2', 2)];
    for (let trial = 0; trial < 200; trial++) {
      const sess = createQuizSession(source);
      expect(sess.questions.length).toBe(3);
      for (let i = 0; i < 3; i++) {
        const q = sess.questions[i];
        const src = source.find((s) => s.id === q.id)!;
        // jumlah opsi SAMA dengan source
        expect(q.options!.length).toBe(src.options!.length);
        // id opsi SAMA set (tidak ada yang hilang/pindah soal)
        const optIds = q.options!.map((o) => o.id).sort();
        const srcIds = src.options!.map((o) => o.id).sort();
        expect(optIds).toEqual(srcIds);
        // text tetap match id-nya (opsi tidak tertukar antar soal)
        for (const o of q.options!) {
          const srcOpt = src.options!.find((s) => s.id === o.id)!;
          expect(o.text).toBe(srcOpt.text);
          expect(o.is_correct).toBe(srcOpt.is_correct);
        }
        // id opsi unik dalam soal
        expect(new Set(optIds).size).toBe(src.options!.length);
      }
    }
  });

  it('setiap soal punya tepat 1 opsi benar', () => {
    const source = [mcq('q-0', 4), mcq('q-1', 5)];
    const sess = createQuizSession(source);
    for (const q of sess.questions) {
      const correct = q.options!.filter((o) => o.is_correct).length;
      expect(correct).toBe(1);
    }
  });

  it('rng=0 menjaga urutan asli (deterministik)', () => {
    const source = [mcq('q-0', 4), mcq('q-1', 3)];
    const sess = createQuizSession(source, () => 0);
    expect(sess.questions.map((q) => q.id)).toEqual(['q-0', 'q-1']);
    expect(sess.questions[0].options!.map((o) => o.id)).toEqual(['q-0-o-0', 'q-0-o-1', 'q-0-o-2', 'q-0-o-3']);
  });
});

function flashcard(id: string): QuizQuestion {
  return { id, type: 'flashcard', front: `F ${id}`, back: `B ${id}`, category: 'evaluasi' } as QuizQuestion;
}

describe('restoreQuizSession (resume attempt guru)', () => {
  it('menyalin jawaban tersimpan by question_id dan recompute is_correct dari source', () => {
    const source = [mcq('q-0', 4, 2), mcq('q-1', 3, 0)];
    // q-0 dijawab benar (opsi index 2), q-1 dijawab salah (opsi index 1)
    const session = restoreQuizSession(
      source,
      [
        { question_id: 'q-0', selected_option_id: 'q-0-o-2', is_correct: false },
        { question_id: 'q-1', selected_option_id: 'q-1-o-1', is_correct: true },
      ],
      () => 0
    );
    expect(session.answers['q-0'].selectedOptionId).toBe('q-0-o-2');
    // is_correct dipercaya dari SOURCE, bukan nilai tersimpan (guard tamper/stale)
    expect(session.answers['q-0'].isCorrect).toBe(true);
    expect(session.answers['q-1'].selectedOptionId).toBe('q-1-o-1');
    expect(session.answers['q-1'].isCorrect).toBe(false);
  });

  it('option_id basi / soal tidak dikenal dianggap belum dijawab dengan aman', () => {
    const source = [mcq('q-0', 4, 0)];
    const session = restoreQuizSession(
      source,
      [
        { question_id: 'q-0', selected_option_id: 'opsi-yang-tidak-ada' },
        { question_id: 'q-hilang', selected_option_id: 'q-hilang-o-0' },
      ],
      () => 0
    );
    expect(session.answers['q-0'].selectedOptionId).toBeNull();
    expect(session.answers['q-0'].isCorrect).toBe(false);
    // soal yang tidak ada di source tidak bocor ke session
    expect(session.answers['q-hilang']).toBeUndefined();
    expect(session.questions.map((q) => q.id)).toEqual(['q-0']);
  });

  it('flashcard tidak menyimpan acknowledged di payload — perlu acknowledge ulang', () => {
    const source = [flashcard('fc-0')];
    const session = restoreQuizSession(
      source,
      [{ question_id: 'fc-0', selected_option_id: null, type: 'flashcard' }],
      () => 0
    );
    expect(session.answers['fc-0'].acknowledged).toBe(false);
  });

  it('mengembalikan sesi bersih bila tidak ada jawaban tersimpan', () => {
    const source = [mcq('q-0', 2)];
    const session = restoreQuizSession(source, [], () => 0);
    expect(session.answers['q-0'].selectedOptionId).toBeNull();
    expect(calculateQuizResult(session).correctMcq).toBe(0);
  });
});

describe('firstUnansweredIndex', () => {
  it('menunjuk soal pertama yang belum dijawab', () => {
    const source = [mcq('q-0', 2), mcq('q-1', 2), mcq('q-2', 2)];
    const session = restoreQuizSession(
      source,
      [
        { question_id: 'q-0', selected_option_id: 'q-0-o-0' },
        { question_id: 'q-1', selected_option_id: 'q-1-o-0' },
      ],
      () => 0
    );
    expect(firstUnansweredIndex(session)).toBe(2);
  });

  it('kembali ke 0 bila semua soal sudah terjawab', () => {
    const source = [mcq('q-0', 2), mcq('q-1', 2)];
    const session = restoreQuizSession(
      source,
      [
        { question_id: 'q-0', selected_option_id: 'q-0-o-0' },
        { question_id: 'q-1', selected_option_id: 'q-1-o-1' },
      ],
      () => 0
    );
    expect(firstUnansweredIndex(session)).toBe(0);
  });
});

describe('Fitur B — model skor rata-rata per jenis', () => {
  it('questionMaxPoints: bobot tertinggi opsi; MCQ biner = 1; flashcard = 0', () => {
    expect(questionMaxPoints(weighted('w', [10, 7, null]))).toBe(10);
    expect(questionMaxPoints(mcq('m', 2))).toBe(1);
    expect(questionMaxPoints({ id: 'f', type: 'flashcard' } as QuizQuestion)).toBe(0);
  });

  it('QUIZ_PASS_THRESHOLD = 75', () => {
    expect(QUIZ_PASS_THRESHOLD).toBe(75);
  });

  it('kuis MCQ saja → statusString "X/Y" (perilaku lama utuh)', () => {
    const sess = createQuizSession([mcq('q-0', 2), mcq('q-1', 2), mcq('q-2', 2)], () => 0);
    answerQuestion(sess, 'q-0', 'q-0-o-0'); // benar
    answerQuestion(sess, 'q-1', 'q-1-o-1'); // salah
    // q-2 tidak dijawab
    const r = calculateQuizResult(sess);
    expect(r.statusString).toBe('1/3');
    expect(r.percent).toBe(33); // round(1/3*100)
    expect(r.hasWeighted).toBe(false);
    expect(r.typeScores.mcq).toEqual({ earned: 1, max: 3, percent: 100 * (1 / 3) });
  });

  it('kuis weighted saja → statusString "P/100" + poin parsial', () => {
    const sess = createQuizSession([weighted('q-0', [10, 7, null]), weighted('q-1', [5, null])], () => 0);
    answerQuestion(sess, 'q-0', 'q-0-o-1'); // [7] → parsial
    answerQuestion(sess, 'q-1', 'q-1-o-0'); // [5] → kunci
    const r = calculateQuizResult(sess);
    expect(r.hasWeighted).toBe(true);
    expect(r.typeScores.weighted.earned).toBe(12);
    expect(r.typeScores.weighted.max).toBe(15);
    expect(r.statusString).toBe('80/100'); // round(12/15*100)
    expect(r.percent).toBe(80);
  });

  it('campuran MCQ + weighted → rata-rata persentase per jenis (Math.round)', () => {
    // MCQ: 2/4 = 50%. Weighted: 17/20 = 85%. Rata2 = 67.5 → 68 (0.5 ke atas).
    const sess = createQuizSession(
      [mcq('m-0', 2), mcq('m-1', 2), mcq('m-2', 2), mcq('m-3', 2), weighted('w-0', [10, 7, null]), weighted('w-1', [10, null])],
      () => 0
    );
    answerQuestion(sess, 'm-0', 'm-0-o-0'); // benar
    answerQuestion(sess, 'm-1', 'm-1-o-0'); // benar
    answerQuestion(sess, 'm-2', 'm-2-o-1'); // salah
    answerQuestion(sess, 'm-3', 'm-3-o-1'); // salah
    answerQuestion(sess, 'w-0', 'w-0-o-1'); // 7/10
    answerQuestion(sess, 'w-1', 'w-1-o-0'); // 10/10
    const r = calculateQuizResult(sess);
    expect(r.typeScores.mcq.percent).toBe(50);
    expect(r.typeScores.weighted.percent).toBe(85);
    expect(r.percent).toBe(68); // Math.round(67.5)
    expect(r.statusString).toBe('68/100');
  });

  it('weighted tidak dijawab → max tetap dihitung, earned 0', () => {
    const sess = createQuizSession([weighted('w-0', [10, null]), weighted('w-1', [10, null])], () => 0);
    answerQuestion(sess, 'w-0', 'w-0-o-0');
    const r = calculateQuizResult(sess);
    expect(r.typeScores.weighted).toEqual({ earned: 10, max: 20, percent: 50 });
    expect(r.statusString).toBe('50/100');
    expect(r.allHandled).toBe(false);
  });

  it('jawaban kosong weighted ([ ]) bernilai 0 poin', () => {
    const sess = createQuizSession([weighted('w-0', [10, 7, null])], () => 0);
    answerQuestion(sess, 'w-0', 'w-0-o-2'); // [ ] → 0
    const r = calculateQuizResult(sess);
    expect(r.typeScores.weighted.earned).toBe(0);
    expect(r.statusString).toBe('0/100');
  });

  it('flashcard saja → percent null, statusString "completed" (auto-lulus)', () => {
    const sess = createQuizSession(
      [{ id: 'f-0', type: 'flashcard', quiz_type: 'flashcard', front: 'F', back: 'B', category: 'evaluasi' } as QuizQuestion],
      () => 0
    );
    const r = calculateQuizResult(sess);
    expect(r.percent).toBeNull();
    expect(r.statusString).toBe('completed');
    expect(r.hasWeighted).toBe(false);
  });

  it('flashcard di kuis campuran tidak mengubah persentase (netral)', () => {
    const source = [
      mcq('m-0', 2),
      { id: 'f-0', type: 'flashcard', quiz_type: 'flashcard', front: 'F', back: 'B', category: 'evaluasi' } as QuizQuestion,
    ];
    const sess = createQuizSession(source, () => 0);
    answerQuestion(sess, 'm-0', 'm-0-o-0');
    const r = calculateQuizResult(sess);
    expect(r.typeScores.mcq.percent).toBe(100);
    expect(r.percent).toBe(100);
    expect(r.statusString).toBe('1/1'); // tanpa weighted → format lama
  });

  it('restoreQuizSession: poin weighted dihitung ulang dari konten', () => {
    const source = [weighted('w-0', [10, 7, null])];
    const sess = restoreQuizSession(
      source,
      [{ question_id: 'w-0', selected_option_id: 'w-0-o-1', is_correct: false, quiz_type: 'weighted' }],
      () => 0
    );
    const a = sess.answers['w-0'];
    expect(a.earnedPoints).toBe(7); // dari source, bukan payload
    expect(a.questionMaxPoints).toBe(10);
    expect(calculateQuizResult(sess).statusString).toBe('70/100');
  });

  it('restoreQuizSession legacy payload (tanpa quiz_type): tetap recompute', () => {
    const source = [mcq('m-0', 2)];
    const sess = restoreQuizSession(
      source,
      [{ question_id: 'm-0', selected_option_id: 'm-0-o-0', is_correct: true }],
      () => 0
    );
    expect(sess.answers['m-0'].earnedPoints).toBe(1);
    expect(calculateQuizResult(sess).statusString).toBe('1/1');
  });
});
