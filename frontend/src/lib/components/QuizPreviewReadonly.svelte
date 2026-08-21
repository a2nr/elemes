<script lang="ts">
	interface QuizOption {
		id: string;
		text: string;
		is_correct: boolean;
	}

	interface QuizQuestion {
		id: string;
		type: 'mcq' | 'flashcard';
		question?: string;
		front?: string;
		back?: string;
		options?: QuizOption[];
		explanation?: string;
		image?: string;
	}

	interface Props {
		quizData: QuizQuestion[];
	}

	let { quizData }: Props = $props();
</script>

<div class="quiz-preview-readonly">
	<h3 class="quiz-preview-title">Preview Kunci Jawaban</h3>
	<p class="quiz-preview-note">Tampilan ini hanya untuk pratinjau — tidak mengirim attempt ke server.</p>

	{#each quizData as question, i (question.id)}
		<div class="quiz-preview-card">
			<div class="quiz-preview-question-header">
				<span class="quiz-preview-number">Soal {i + 1}</span>
				<span class="quiz-preview-type" class:flashcard={question.type === 'flashcard'}>
					{question.type === 'mcq' ? 'Pilihan Ganda' : 'Flashcard'}
				</span>
			</div>

			{#if question.image}
				<img src={question.image} alt="Ilustrasi soal" class="quiz-preview-image" />
			{/if}

			<div class="quiz-preview-question">
				{@html question.question ?? question.front ?? ''}
			</div>

			{#if question.type === 'mcq' && question.options}
				<div class="quiz-preview-options">
					{#each question.options as option (option.id)}
						<div class="quiz-preview-option" class:correct={option.is_correct}>
							<span class="option-marker" class:correct-marker={option.is_correct}>
								{option.is_correct ? '✓' : '○'}
							</span>
							<span class="option-text">{@html option.text}</span>
						</div>
					{/each}
				</div>
			{:else if question.type === 'flashcard'}
				<div class="quiz-preview-flashcard">
					<div class="flashcard-label">Jawaban:</div>
					<div class="flashcard-back">{@html question.back ?? ''}</div>
				</div>
			{/if}

			{#if question.explanation}
				<div class="quiz-preview-explanation">
					<strong>Penjelasan:</strong>
					{@html question.explanation}
				</div>
			{/if}
		</div>
	{/each}

	{#if quizData.length === 0}
		<p class="quiz-preview-empty">Tidak ada data kuis untuk ditampilkan.</p>
	{/if}
</div>

<style>
	.quiz-preview-readonly {
		padding: 1rem;
		font-size: 0.9rem;
	}
	.quiz-preview-title {
		font-size: 1.1rem;
		color: var(--color-primary, #339af0);
		margin: 0 0 0.25rem;
	}
	.quiz-preview-note {
		font-size: 0.8rem;
		color: var(--color-text-muted, #868e96);
		margin: 0 0 1rem;
	}
	.quiz-preview-card {
		border: 1px solid var(--color-border, #dee2e6);
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1rem;
		background: var(--color-bg-secondary, #f8f9fa);
	}
	.quiz-preview-question-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	.quiz-preview-number {
		font-weight: 700;
		color: var(--color-primary, #339af0);
	}
	.quiz-preview-type {
		font-size: 0.75rem;
		padding: 2px 8px;
		border-radius: 999px;
		background: var(--color-bg, #fff);
		border: 1px solid var(--color-border, #dee2e6);
	}
	.quiz-preview-type.flashcard {
		color: #e67700;
		border-color: #fcc419;
	}
	.quiz-preview-image {
		max-width: 100%;
		max-height: 200px;
		object-fit: contain;
		border-radius: 8px;
		margin-bottom: 0.75rem;
	}
	.quiz-preview-question {
		margin-bottom: 0.75rem;
		line-height: 1.6;
	}
	.quiz-preview-options {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-bottom: 0.75rem;
	}
	.quiz-preview-option {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		padding: 0.5rem;
		border-radius: 6px;
		border: 1px solid var(--color-border, #dee2e6);
		background: var(--color-bg, #fff);
	}
	.quiz-preview-option.correct {
		border-color: #40c057;
		background: #ebfbee;
	}
	.option-marker {
		flex-shrink: 0;
		font-weight: 700;
	}
	.correct-marker {
		color: #40c057;
	}
	.option-text {
		flex: 1;
		line-height: 1.5;
	}
	.quiz-preview-flashcard {
		padding: 0.75rem;
		background: var(--color-bg, #fff);
		border-radius: 6px;
		border: 1px solid var(--color-border, #dee2e6);
		margin-bottom: 0.75rem;
	}
	.flashcard-label {
		font-weight: 600;
		color: var(--color-text-muted, #868e96);
		margin-bottom: 0.25rem;
		font-size: 0.8rem;
	}
	.quiz-preview-explanation {
		padding: 0.5rem;
		background: #fff9db;
		border-radius: 6px;
		border: 1px solid #fcc419;
		font-size: 0.85rem;
		line-height: 1.5;
	}
	.quiz-preview-empty {
		color: var(--color-text-muted, #868e96);
		text-align: center;
		padding: 2rem;
	}
</style>
