import { describe, it, expect } from 'vitest';
import {
  createQuizSession,
  calculateQuizResult,
  restoreQuizSession,
  firstUnansweredIndex,
} from './quiz-session';
import type { QuizQuestion } from '../types/quiz';

function mcq(id: string, nOpts: number, correctIdx = 0): QuizQuestion {
  const options = Array.from({ length: nOpts }, (_, i) => ({
    id: `${id}-o-${i}`,
    text: `opt ${i}`,
    is_correct: i === correctIdx,
  }));
  return {
    id,
    type: 'mcq',
    question: `Q ${id}`,
    options,
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
