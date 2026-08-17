<script lang="ts">
	import { authLoggedIn, authToken } from '$stores/auth';
	import { get } from 'svelte/store';
	import { onMount } from 'svelte';
	import { renderMath } from '$lib/actions/renderMath';
	import { shouldShowQuizReview } from '$services/quiz-integrity';
	import type { LessonManager } from './lesson.svelte';
	import type { QuizQuestion, QuizAnswer } from '$types/quiz';
	import { fetchQuizAttempt } from '$services/api';
	import type { QuizAttemptFetchResponse } from '$services/api';

	interface Props {
		mgr: LessonManager;
	}

	let { mgr }: Props = $props();

	const isLoggedIn = $derived($authLoggedIn);
	// Gate 2: Quiz already completed (one-attempt enforcement)
	const quizAlreadyCompleted = $derived(
		!!mgr.data?.lesson_progress_status &&
			mgr.data.lesson_progress_status !== 'not_started' &&
			mgr.data.lesson_progress_status !== ''
	);

	const currentQuestion = $derived(mgr.currentQuizQuestion);
	const currentAnswer = $derived(mgr.currentQuizAnswer);
	const questions = $derived(mgr.quizSession?.questions ?? []);
	const result = $derived(mgr.quizResult);
	// Strict policy: kuis yang dihentikan karena focus_lost tidak menampilkan
	// pembahasan (siswa yang kehilangan fokus tidak mendapat bocoran jawaban).
	const showReview = $derived(shouldShowQuizReview(mgr.quizTerminationReason));

	// --- Review-after-refresh: fetch stored attempt (one-attempt → session lost) ---
	let storedAttempt: QuizAttemptFetchResponse | null = $state(null);
	let reviewQuestions: QuizQuestion[] = $state([]);
	let reviewAnswers: Record<string, QuizAnswer> = $state({});

	async function loadStoredAttempt() {
		const token = get(authToken) || localStorage.getItem('student_token') || '';
		if (!token || !mgr.data) return;
		const lessonName = mgr.slug.replace('.md', '');
		try {
			const resp = await fetchQuizAttempt(token, lessonName);
			if (resp.success && resp.answers?.length) {
				storedAttempt = resp;
				// Rekonstruksi question+answer maps dari stored attempt agar
				// summary review per-soal bisa dirender setelah refresh.
				const src = mgr.data?.quiz_data ?? [];
				// Cocokkan by question_id; gunakan urutan asli (parser order).
				reviewQuestions = src.filter((q) => resp.answers.some((a) => a.question_id === q.id));
				reviewAnswers = {};
				for (const ans of resp.answers) {
					const q = src.find((qq) => qq.id === ans.question_id);
					if (q) {
						reviewAnswers[q.id] = {
							questionId: q.id,
							selectedOptionId: ans.selected_option_id,
							acknowledged: false,
							isCorrect: ans.is_correct,
						};
					}
				}
			}
		} catch {
			// best-effort; review akan tetap tersedia di session bila masih hidup
		}
	}

	// Fetch attempt bila sudah selesai tapi session hilang (refresh/page-open)
	onMount(() => {
		const r = result;
		if (!r && quizAlreadyCompleted && !mgr.quizSession) {
			loadStoredAttempt();
		}
	});

	function handleExit() {
		if (!mgr.isQuizMode) return;

		const unanswered = mgr.quizTotalCount - mgr.quizAnsweredCount;
		let confirmMsg = 'Yakin keluar dari kuis?';
		if (unanswered > 0) {
			confirmMsg += ` ${unanswered} soal belum dijawab dan akan dianggap salah.`;
		}
		confirmMsg += ' Skor akan disimpan dan tidak bisa diulang.';

		if (window.confirm(confirmMsg)) {
			mgr.submitQuiz();
		}
	}
</script>

<div class="quiz-container">
	{#if result || quizAlreadyCompleted}
		<div class="summary-view" use:renderMath>
			<div class="summary-header">
				<div class="summary-icon">🏁</div>
				<h2>Kuis Selesai!</h2>
				{#if quizAlreadyCompleted && !result}
					{#if storedAttempt}
						{@const s = storedAttempt}
						<p class="score-display">Nilai Anda: <strong>{s.score}</strong></p>
						<div class="score-breakdown">
							<span class="breakdown-item">Evaluasi: <strong>{s.score_earned ?? '-'}/{s.score_total ?? '-'}</strong></span>
						</div>
					{:else}
						<p class="score-display">Nilai Anda: <strong>{mgr.data?.lesson_progress_status}</strong></p>
					{/if}
					<div class="alert alert-info">
						Kuis ini sudah diselesaikan. Silakan hubungi guru jika ingin mengulang.
					</div>
				{:else if result}
					{@const totalMcq = result.totalMcq}
					{#if mgr.quizTerminationReason === 'focus_lost'}
						<div class="alert alert-danger">
							Kuis dihentikan karena halaman kehilangan fokus. Skor disimpan dan percobaann tidak dapat diulang.
						</div>
					{:else if mgr.quizTerminationReason === 'page_unload'}
						<div class="alert alert-danger">
							Kuis dihentikan karena halaman di-refresh atau ditutup. Skor disimpan dan percobaan tidak dapat diulang.
						</div>
					{/if}
					{@const correct = result.correctMcq}
					<p class="score-display">Skor: <strong>{correct} / {totalMcq}</strong></p>

					{#if totalMcq > 0 && correct / totalMcq < 0.75}
						<div class="alert alert-warning">
							Nilai Anda di bawah ambang batas 75%. Pelajari kembali topik di bawah ini.
						</div>
					{:else}
						<div class="alert alert-success">
							Selamat! Anda telah memahami materi ini dengan baik.
						</div>
					{/if}

					{#if result.evalTotal > 0 || result.diagTotal > 0}
						<div class="score-breakdown">
							{#if result.evalTotal > 0}
								<span class="breakdown-item">Evaluasi: <strong>{result.evalCorrect}/{result.evalTotal}</strong></span>
							{/if}
							{#if result.diagTotal > 0}
								<span class="breakdown-item">Diagnostik: <strong>{result.diagCorrect}/{result.diagTotal}</strong></span>
								{#if result.diagUnmastered.length > 0}
									<span class="breakdown-item unmastered">
										Belum dikuasai:
										{#each result.diagUnmastered as q}
											<span class="unmastered-topic">{(q.front ?? q.question ?? 'Soal').replace(/<[^>]*>/g, '').slice(0, 40)}</span>
										{/each}
									</span>
								{/if}
							{/if}
						</div>
					{/if}

					{#if showReview && questions.length > 0}
						<div class="summary-review">
							<h3 class="review-title">Pembahasan</h3>
							{#each questions as q, i}
								{@const a = mgr.quizSession!.answers[q.id]}
								<div class="review-item" data-category={q.category ?? 'evaluasi'}>
									<div class="review-header">
										<span class="review-number">Soal {i + 1} <span class="review-category-badge">{q.category === 'diagnostik' ? 'Diagnostik' : 'Evaluasi'}</span></span>
										{#if q.type === 'mcq'}
											<span class="review-badge" class:ok={a.isCorrect} class:bad={!a.isCorrect}>
												{a.isCorrect ? '✓ Benar' : '✗ Salah'}
											</span>
										{:else}
											<span class="review-badge ok">Selesai</span>
										{/if}
									</div>
									<div class="review-question">{@html q.question ?? q.front ?? ''}</div>
									{#if q.type === 'mcq' && q.options}
										<div class="review-options">
											{#each q.options as opt}
												<div
													class="review-option"
													class:chosen={opt.id === a.selectedOptionId}
													class:correct-opt={opt.is_correct}
												>
													<span class="review-option-mark">
														{opt.is_correct ? '✅' : opt.id === a.selectedOptionId ? '❌' : '○'}
													</span>
													<span class="review-option-text">{@html opt.text}</span>
												</div>
											{/each}
										</div>
										{#if !a.isCorrect && a.selectedOptionId === null}
											<p class="review-unanswered">Tidak dijawab — dianggap salah.</p>
										{/if}
									{:else}
										<div class="review-back">{@html q.back ?? ''}</div>
										{#if !a.acknowledged}
											<p class="review-unanswered">Tidak ditandai dipahami.</p>
										{:else if a.understood === false}
											<p class="review-not-understood">❓ Siswa tidak mengerti materi ini.</p>
										{/if}
									{/if}
									{#if q.explanation}
										<div class="explanation-box">{@html q.explanation}</div>
									{/if}
								</div>
							{/each}
						</div>
					{:else if !showReview && questions.length > 0}
						<p class="review-hidden-note">
							🔒 Pembahasan disembunyikan karena kuis dihentikan saat halaman kehilangan fokus.
						</p>
					{/if}
				{/if}

				{#if storedAttempt && !result && shouldShowQuizReview(storedAttempt.termination_reason) && reviewQuestions.length > 0}
					<div class="summary-review">
						<h3 class="review-title">Pembahasan (tersimpan)</h3>
						{#each reviewQuestions as q, i}
							{@const a = reviewAnswers[q.id]}
							<div class="review-item" data-category={q.category ?? 'evaluasi'}>
								<div class="review-header">
									<span class="review-number">Soal {i + 1} <span class="review-category-badge">{q.category === 'diagnostik' ? 'Diagnostik' : 'Evaluasi'}</span></span>
									{#if q.type === 'mcq'}
										<span class="review-badge" class:ok={a.isCorrect} class:bad={!a.isCorrect}>
											{a.isCorrect ? '✓ Benar' : '✗ Salah'}
										</span>
									{:else}
										<span class="review-badge ok">Selesai</span>
									{/if}
								</div>
								<div class="review-question">{@html q.question ?? q.front ?? ''}</div>
								{#if q.type === 'mcq' && q.options}
									<div class="review-options">
										{#each q.options as opt}
											<div
												class="review-option"
												class:chosen={opt.id === a.selectedOptionId}
												class:correct-opt={opt.is_correct}
											>
												<span class="review-option-mark">
													{opt.is_correct ? '✅' : opt.id === a.selectedOptionId ? '❌' : '○'}
												</span>
												<span class="review-option-text">{@html opt.text}</span>
											</div>
										{/each}
									</div>
									{#if !a.isCorrect && a.selectedOptionId === null}
										<p class="review-unanswered">Tidak dijawab — dianggap salah.</p>
									{/if}
								{:else}
									<div class="review-back">{@html q.back ?? ''}</div>
								{/if}
								{#if q.explanation}
									<div class="explanation-box">{@html q.explanation}</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	{:else if !mgr.isQuizMode}
		<div class="quiz-start-view">
			<div class="quiz-icon">📝</div>
			<h2>Kuis Interaktif</h2>
			<p>Uji pemahamanmu dengan kuis ini.</p>

			{#if !isLoggedIn}
				<div class="alert alert-warning">
					⚠️ <strong>Login diperlukan.</strong> Klik tombol login di navbar atas untuk memulai kuis.
				</div>
				<button class="btn btn-primary btn-lg" disabled>
					Mulai Kuis Sekarang
				</button>
			{:else}
				<div class="alert alert-warning">
					⚠️ <strong>Penting:</strong> Materi pelajaran akan disembunyikan. Kamu harus menjawab semua soal untuk dapat menyelesaikannya. Jika keluar di tengah kuis, soal yang belum dijawab akan dianggap <strong>salah</strong>.
				</div>
				<button class="btn btn-primary btn-lg" onclick={() => mgr.startQuiz()}>
					Mulai Kuis Sekarang
				</button>
			{/if}
		</div>
	{:else if questions.length > 0}
		<div class="quiz-active-view">
			<div class="answer-sheet">
				{#if currentQuestion?.type === 'mcq'}
					<p class="answer-sheet-label">Pilih jawabanmu</p>
					<div class="options-grid" class:single-col={(currentQuestion.options?.length ?? 0) <= 2}>
						{#each currentQuestion.options ?? [] as option, i}
							<button
								type="button"
								class="option-btn"
								class:selected={currentAnswer?.selectedOptionId === option.id}
								aria-pressed={currentAnswer?.selectedOptionId === option.id}
								onclick={() => mgr.selectQuizOption(option.id)}
							>
								<div class="option-marker">{String.fromCharCode(65 + i)}</div>
								<div class="option-text">{@html option.text}</div>
							</button>
						{/each}
					</div>
					<p class="answer-hint">Pilihan bisa diganti sebelum kuis diselesaikan.</p>
				{:else if currentQuestion?.type === 'flashcard'}
					<div class="flashcard-ack-view">
						<button
							type="button"
							class="btn-flashcard-ok"
							class:selected={currentAnswer?.acknowledged && currentAnswer?.understood !== false}
							onclick={() => mgr.acknowledgeFlashcard(true)}
						>
							✅ Sudah Mengerti
						</button>
						<button
							type="button"
							class="btn-flashcard-no"
							class:selected={currentAnswer?.acknowledged && currentAnswer?.understood === false}
							onclick={() => mgr.acknowledgeFlashcard(false)}
						>
							❓ Tidak Mengerti
						</button>
					</div>
				{/if}
			</div>

			<div class="cancel-container">
				<button type="button" class="btn-exit-quiz" onclick={handleExit}>Keluar Kuis</button>
				<span class="cancel-lock-hint">⚠️ Keluar = selesai. Soal belum dijawab dianggap salah.</span>
			</div>
		</div>
	{:else}
		<div class="quiz-empty"><p>Tidak ada data kuis.</p></div>
	{/if}
</div>

<style>
	.quiz-container {
		flex: 1;
		min-height: 0;
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		background: var(--color-bg);
		overflow-y: auto;
	}

	.summary-view {
		text-align: center;
		padding: 2rem 1rem;
		max-width: 640px;
		margin: auto;
		width: 100%;
	}
	.summary-icon { font-size: 4rem; margin-bottom: 1rem; }
	.score-display { font-size: 1.5rem; margin-bottom: 1.5rem; }
	.score-display strong { color: var(--color-primary); font-size: 2.5rem; }

	.quiz-active-view { flex: 1; display: flex; flex-direction: column; gap: 1.25rem; }
	.quiz-start-view { text-align: center; max-width: 400px; margin: auto; display: flex; flex-direction: column; gap: 1rem; }
	.quiz-icon { font-size: 4rem; margin-bottom: 0.5rem; }

	.alert { padding: 1rem; border-radius: 8px; font-size: 0.9rem; line-height: 1.4; text-align: left; }
	.alert-warning { background: var(--color-bg-secondary); border: 1px solid var(--color-warning); color: var(--color-text); }
	.alert-success { background: rgba(25, 135, 84, 0.1); border: 1px solid var(--color-success); color: var(--color-success); }
	.alert-info { background: rgba(13, 110, 253, 0.1); border: 1px solid var(--color-primary); color: var(--color-primary); }
	.alert-danger { background: rgba(233, 236, 239, 0.5); border: 1px solid var(--color-danger, #dc3545); color: var(--color-danger, #dc3545); }

	.answer-sheet { flex: 1; display: flex; flex-direction: column; gap: 1rem; }
	.answer-sheet-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-muted); font-weight: 700; }
	.options-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}
	.options-grid.single-col {
		grid-template-columns: 1fr;
	}
	.option-btn { display: flex; align-items: flex-start; gap: 0.75rem; padding: 0.85rem; background: var(--color-bg); border: 2px solid var(--color-border); border-radius: 12px; cursor: pointer; text-align: left; transition: all 0.2s; font-size: 1rem; color: var(--color-text); align-self: stretch; }
	.option-btn:hover { border-color: var(--color-primary); background: var(--color-bg-secondary); }
	.option-btn.selected { border-color: var(--color-primary); background: var(--color-bg-secondary); box-shadow: 0 0 0 2px rgba(51, 154, 240, 0.15); }
	.option-marker { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 8px; font-weight: 700; font-size: 0.9rem; flex-shrink: 0; color: var(--color-text); }
	.option-btn.selected .option-marker { background: var(--color-primary); border-color: var(--color-primary); color: white; }
	.option-text { flex: 1; }
	.option-text :global(img) { max-width: 100%; height: auto; border-radius: 4px; display: block; margin: 0.5rem 0; }
	.answer-hint { font-size: 0.8rem; color: var(--color-text-muted); font-style: italic; }

	.flashcard-ack-view {
		display: flex;
		flex-direction: row;
		gap: 0.75rem;
		justify-content: center;
		flex-wrap: wrap;
		padding: 1rem 0;
	}
	.btn-flashcard-ok {
		flex: 1;
		min-width: 120px;
		max-width: 200px;
		padding: 0.8rem 1rem;
		border-radius: 10px;
		border: 2px solid var(--color-success, #40c057);
		background: transparent;
		color: var(--color-success, #40c057);
		font-weight: 600;
		font-size: 0.95rem;
		cursor: pointer;
		transition: all 0.15s;
	}
	.btn-flashcard-ok:hover,
	.btn-flashcard-ok.selected {
		background: var(--color-success, #40c057);
		color: white;
	}
	.btn-flashcard-no {
		flex: 1;
		min-width: 120px;
		max-width: 200px;
		padding: 0.8rem 1rem;
		border-radius: 10px;
		border: 2px solid var(--color-warning, #fab005);
		background: transparent;
		color: var(--color-warning, #fab005);
		font-weight: 600;
		font-size: 0.95rem;
		cursor: pointer;
		transition: all 0.15s;
	}
	.btn-flashcard-no:hover,
	.btn-flashcard-no.selected {
		background: var(--color-warning, #fab005);
		color: white;
	}

	.btn { padding: 0.6rem 1.2rem; border-radius: 8px; font-weight: 600; cursor: pointer; border: none; transition: opacity 0.2s; }
	.btn:disabled { opacity: 0.5; cursor: not-allowed; }
	.btn-primary { background: #339af0; color: white; }
	.btn-success { background: #40c057; color: white; }
	.btn-lg { padding: 1rem 2rem; font-size: 1.1rem; }

	.btn-exit-quiz { background: none; border: none; color: var(--color-danger, #dc3545); text-decoration: underline; font-size: 0.85rem; cursor: pointer; }

	.btn-exit-quiz:hover { color: #c82333; }
	.cancel-container { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; }
	.cancel-lock-hint { font-size: 0.75rem; color: var(--color-danger, #dc3545); font-weight: 500; }
	.quiz-empty { text-align: center; margin: auto; color: var(--color-text-muted); }

	/* Summary review */
	.summary-review { text-align: left; margin-top: 2rem; }
	.review-title { font-size: 1.1rem; margin-bottom: 1rem; color: var(--color-text); }
	.review-item { border: 1px solid var(--color-border); border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem; background: var(--color-bg); }
	.review-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; }
	.review-number { font-weight: 700; font-size: 0.85rem; color: var(--color-text-muted); text-transform: uppercase; letter-spacing: 0.03em; }
	.review-badge { font-size: 0.75rem; font-weight: 700; padding: 0.25rem 0.6rem; border-radius: 999px; }
	.review-badge.ok { background: rgba(25, 135, 84, 0.12); color: var(--color-success); }
	.review-badge.bad { background: rgba(220, 53, 69, 0.12); color: var(--color-danger); }
	.review-question { font-weight: 600; margin-bottom: 0.75rem; line-height: 1.5; }
	.review-question :global(img) { max-width: 100%; height: auto; border-radius: 8px; }
	.review-options { display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 0.5rem; }
	.review-option { display: flex; align-items: flex-start; gap: 0.6rem; padding: 0.6rem 0.75rem; border: 1px solid var(--color-border); border-radius: 8px; font-size: 0.9rem; }
	.review-option.chosen:not(.correct-opt) { border-color: var(--color-danger); background: rgba(220, 53, 69, 0.06); }
	.review-option.correct-opt { border-color: var(--color-success); background: rgba(25, 135, 84, 0.08); }
	.review-option-text :global(img) { max-width: 100%; height: auto; border-radius: 4px; }
	.review-unanswered { font-size: 0.8rem; color: var(--color-danger); font-style: italic; margin: 0.5rem 0; }
	.review-not-understood { font-size: 0.8rem; color: var(--color-warning, #fab005); font-style: italic; margin: 0.5rem 0; }
	.review-hidden-note { font-size: 0.9rem; color: var(--color-text-muted); padding: 1rem; background: var(--color-bg-secondary); border: 1px dashed var(--color-border); border-radius: 8px; margin-top: 1rem; text-align: center; }
	.review-back { padding: 0.75rem; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 8px; font-size: 0.9rem; }
	.explanation-box { font-size: 0.85rem; line-height: 1.5; padding: 1rem; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 8px; text-align: left; margin-top: 0.5rem; }
	.explanation-box :global(p) { margin: 0; }

	.score-breakdown { display: flex; flex-wrap: wrap; gap: 0.75rem; justify-content: center; margin: 0.75rem 0 1.25rem; }
	.breakdown-item { font-size: 0.95rem; padding: 0.35rem 0.7rem; border-radius: 999px; background: var(--color-bg-secondary); border: 1px solid var(--color-border); }
	.breakdown-item strong { color: var(--color-primary); }
	.breakdown-item.unmastered { flex-basis: 100%; justify-content: center; }
	.unmastered-topic { font-size: 0.8rem; background: rgba(220, 53, 69, 0.1); color: var(--color-danger); padding: 0.15rem 0.5rem; border-radius: 6px; margin: 0.15rem; display: inline-block; }

	@media (max-width: 400px) {
		.options-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 600px) {
		.option-btn { padding: 0.75rem; font-size: 0.95rem; }
		.quiz-container { padding: 1rem; }
	}
</style>
