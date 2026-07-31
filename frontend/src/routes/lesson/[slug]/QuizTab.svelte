<script lang="ts">
	import { authLoggedIn } from '$stores/auth';
	import { renderMath } from '$lib/actions/renderMath';
	import type { LessonManager } from './lesson.svelte';

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

	function handleFinish() {
		if (!mgr.quizAllAnswered) return;

		if (window.confirm('Apakah anda yakin untuk menyelesaikan kuis? Materi akan muncul kembali setelah ini.')) {
			mgr.finishQuiz();
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
					<p class="score-display">Nilai Anda: <strong>{mgr.data?.lesson_progress_status}</strong></p>
					<div class="alert alert-info">
						Kuis ini sudah diselesaikan. Silakan hubungi guru jika ingin mengulang.
					</div>
				{:else if result}
					{@const totalMcq = result.totalMcq}
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

					{#if questions.length > 0}
						<div class="summary-review">
							<h3 class="review-title">Pembahasan</h3>
							{#each questions as q, i}
								{@const a = mgr.quizSession!.answers[q.id]}
								<div class="review-item">
									<div class="review-header">
										<span class="review-number">Soal {i + 1}</span>
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
										{/if}
									{/if}
									{#if q.explanation}
										<div class="explanation-box">{@html q.explanation}</div>
									{/if}
								</div>
							{/each}
						</div>
					{/if}
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
			<div class="quiz-progress">
				Pertanyaan {mgr.quizCurrentIndex + 1} dari {questions.length}
				<span class="quiz-progress-answered">{mgr.quizAnsweredCount} dijawab</span>
				<div class="progress-bar-bg">
					<div
						class="progress-bar-fill"
						style="width: {((mgr.quizAnsweredCount / questions.length) * 100).toFixed(1)}%"
					></div>
				</div>
			</div>

			<div class="answer-sheet">
				{#if currentQuestion?.type === 'mcq'}
					<p class="answer-sheet-label">Pilih jawabanmu</p>
					<div class="options-grid">
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
						<p class="answer-sheet-label">Sudah paham materi ini?</p>
						<p class="answer-hint">Baca soal di panel kiri. Jawaban dari kartu ini hanya ditampilkan di pembahasan setelah kuis selesai.</p>
						<button
							type="button"
							class="btn btn-primary btn-lg ack-btn"
							class:acknowledged={currentAnswer?.acknowledged}
							onclick={() => mgr.acknowledgeFlashcard()}
						>
							{currentAnswer?.acknowledged ? '✅ Sudah dipahami' : 'Tandai sudah dipahami'}
						</button>
					</div>
				{/if}
			</div>

			<div class="quiz-navigator" aria-label="Navigasi soal">
				{#each questions as q, i}
					{@const answered = mgr.quizSession!.answers[q.id].selectedOptionId !== null || mgr.quizSession!.answers[q.id].acknowledged}
					<button
						type="button"
						class="nav-dot"
						class:active={i === mgr.quizCurrentIndex}
						class:answered={answered}
						aria-label={`Soal ${i + 1}${answered ? ' (dijawab)' : ' (belum dijawab)'}`}
						aria-current={i === mgr.quizCurrentIndex ? 'step' : undefined}
						onclick={() => mgr.goToQuizQuestion(i)}
					>
						{i + 1}
					</button>
				{/each}
			</div>

			<div class="quiz-controls">
				<button
					type="button"
					class="btn btn-outline"
					onclick={() => mgr.prevQuizQuestion()}
					disabled={mgr.quizCurrentIndex === 0}
				>
					← Sebelumnya
				</button>
				{#if mgr.quizCurrentIndex < questions.length - 1}
					<button type="button" class="btn btn-primary" onclick={() => mgr.nextQuizQuestion()}>
						Selanjutnya →
					</button>
				{:else}
					<button type="button" class="btn btn-success" onclick={handleFinish} disabled={!mgr.quizAllAnswered}>
						Selesai Kuis
					</button>
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

	.quiz-progress { font-size: 0.85rem; color: var(--color-text-muted); }
	.quiz-progress-answered { margin-left: 0.75rem; }
	.progress-bar-bg { height: 6px; background: var(--color-border); border-radius: 3px; margin-top: 0.5rem; overflow: hidden; }
	.progress-bar-fill { height: 100%; background: var(--color-primary, #339af0); transition: width 0.3s ease; }

	.answer-sheet { flex: 1; display: flex; flex-direction: column; gap: 1rem; }
	.answer-sheet-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-muted); font-weight: 700; }
	.options-grid { display: flex; flex-direction: column; gap: 0.75rem; }
	.option-btn { display: flex; align-items: center; gap: 1rem; padding: 1rem; background: var(--color-bg); border: 2px solid var(--color-border); border-radius: 12px; cursor: pointer; text-align: left; transition: all 0.2s; font-size: 1rem; color: var(--color-text); }
	.option-btn:hover { border-color: var(--color-primary); background: var(--color-bg-secondary); }
	.option-btn.selected { border-color: var(--color-primary); background: var(--color-bg-secondary); box-shadow: 0 0 0 2px rgba(51, 154, 240, 0.15); }
	.option-marker { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 8px; font-weight: 700; font-size: 0.9rem; flex-shrink: 0; color: var(--color-text); }
	.option-btn.selected .option-marker { background: var(--color-primary); border-color: var(--color-primary); color: white; }
	.option-text { flex: 1; }
	.option-text :global(img) { max-width: 100%; height: auto; border-radius: 4px; display: block; margin: 0.5rem 0; }
	.answer-hint { font-size: 0.8rem; color: var(--color-text-muted); font-style: italic; }

	.flashcard-ack-view { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1rem; text-align: center; flex: 1; padding: 2rem 1rem; background: var(--color-bg-secondary); border: 2px dashed var(--color-border); border-radius: 16px; }
	.ack-btn.acknowledged { background: var(--color-success); }

	.quiz-navigator { display: flex; flex-wrap: wrap; gap: 0.4rem; }
	.nav-dot { width: 34px; height: 34px; border-radius: 8px; border: 1px solid var(--color-border); background: var(--color-bg); color: var(--color-text); font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: all 0.15s; }
	.nav-dot:hover { border-color: var(--color-primary); }
	.nav-dot.answered { background: rgba(51, 154, 240, 0.15); border-color: var(--color-primary); color: var(--color-primary); }
	.nav-dot.active { background: var(--color-primary); border-color: var(--color-primary); color: white; }

	.quiz-controls {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		position: relative;
		z-index: 10;
		background: var(--color-bg);
		padding-top: 1rem;
	}
	.btn { padding: 0.6rem 1.2rem; border-radius: 8px; font-weight: 600; cursor: pointer; border: none; transition: opacity 0.2s; }
	.btn:disabled { opacity: 0.5; cursor: not-allowed; }
	.btn-primary { background: #339af0; color: white; }
	.btn-success { background: #40c057; color: white; }
	.btn-outline { background: white; border: 1px solid var(--color-border); color: var(--color-text); }
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
	.review-back { padding: 0.75rem; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 8px; font-size: 0.9rem; }
	.explanation-box { font-size: 0.85rem; line-height: 1.5; padding: 1rem; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 8px; text-align: left; margin-top: 0.5rem; }
	.explanation-box :global(p) { margin: 0; }

	@media (max-width: 600px) {
		.option-btn { padding: 0.75rem; font-size: 0.95rem; }
		.quiz-container { padding: 1rem; }
	}
</style>
