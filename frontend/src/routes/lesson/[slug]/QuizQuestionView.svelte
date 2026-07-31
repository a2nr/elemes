<script lang="ts">
	import type { QuizQuestion } from '$types/quiz';

	interface Props {
		question: QuizQuestion | null;
		currentIndex: number;
		totalCount: number;
		answeredCount: number;
		onExit: () => void;
	}

	let { question, currentIndex, totalCount, answeredCount, onExit }: Props = $props();
</script>

<div class="quiz-question-view">
	<div class="quiz-question-header">
		<span class="quiz-question-counter">Soal {currentIndex + 1} dari {totalCount}</span>
		<span class="quiz-question-answered">{answeredCount} dijawab</span>
		<button type="button" class="btn-exit-quiz" onclick={onExit}>Keluar Kuis</button>
	</div>
	<div class="quiz-question-progress" aria-hidden="true">
		<div
			class="progress-bar-fill"
			style="width: {((answeredCount / Math.max(totalCount, 1)) * 100).toFixed(1)}%"
		></div>
	</div>

	{#if question}
		<div class="quiz-question-prose">
			{#if question.image}
				<img src={question.image} alt="Ilustrasi soal" class="quiz-question-image" />
			{/if}
			<!-- Hanya prompt soal (question/front). Opsi, jawaban, dan penjelasan
			     TIDAK pernah dirender di sini — itu bagian lembar jawaban/summary. -->
			{@html question.question ?? question.front ?? ''}
		</div>
	{:else}
		<p class="quiz-empty">Tidak ada soal.</p>
	{/if}
</div>
