<script lang="ts">
	import type { LessonManager } from './lesson.svelte';

	interface Props {
		mgr: LessonManager;
	}

	let { mgr }: Props = $props();

	const questions = $derived(mgr.quizSession?.questions ?? []);

	function isAnswered(qId: string): boolean {
		const a = mgr.quizSession?.answers[qId];
		if (!a) return false;
		return a.selectedOptionId !== null || a.acknowledged;
	}

	function handleFinish() {
		if (!mgr.quizAllAnswered) return;

		if (
			window.confirm(
				'Apakah anda yakin untuk menyelesaikan kuis? Materi akan muncul kembali setelah ini.'
			)
		) {
			mgr.finishQuiz();
		}
	}
</script>

<div class="quiz-question-view">
	<div class="quiz-question-header">
		{#if questions.length > 0}
			<div class="quiz-navigator" aria-label="Navigasi soal">
				{#each questions as q, i}
					{@const answered = isAnswered(q.id)}
					<button
						type="button"
						class="nav-dot"
						class:active={i === mgr.quizCurrentIndex}
						class:answered
						aria-label={`Soal ${i + 1}${answered ? ' (dijawab)' : ' (belum dijawab)'}`}
						aria-current={i === mgr.quizCurrentIndex ? 'step' : undefined}
						onclick={() => mgr.goToQuizQuestion(i)}
					>
						{i + 1}
					</button>
				{/each}
			</div>
		{/if}
		<button type="button" class="btn-exit-quiz" onclick={() => mgr.submitQuiz()}>Keluar Kuis</button>
	</div>

	{#if mgr.quizCurrentQuestion}
		<div class="quiz-question-prose">
			{#if mgr.quizCurrentQuestion.image}
				<img
					src={mgr.quizCurrentQuestion.image}
					alt="Ilustrasi soal"
					class="quiz-question-image"
				/>
			{/if}
			<!-- Hanya prompt soal (question/front). Opsi, jawaban, dan penjelasan
			     TIDAK pernah dirender di sini — itu bagian lembar jawaban/summary. -->
			{@html mgr.quizCurrentQuestion.question ?? mgr.quizCurrentQuestion.front ?? ''}
		</div>
	{:else}
		<p class="quiz-empty">Tidak ada soal.</p>
	{/if}

	{#if questions.length > 0}
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
				<button
					type="button"
					class="btn btn-success"
					onclick={handleFinish}
					disabled={!mgr.quizAllAnswered}
				>
					Selesai Kuis
				</button>
			{/if}
		</div>
	{/if}
</div>
