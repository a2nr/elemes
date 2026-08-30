import { describe, it, expect } from 'vitest';
import { createQuizSession, calculateQuizResult } from './quiz-session';
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
