<script lang="ts">
	interface Option {
		text: string;
		is_correct: boolean;
	}

	interface FlashcardData {
		type: 'flashcard' | 'mcq';
		front?: string;
		back?: string;
		question?: string;
		options?: Option[];
		explanation?: string;
	}

	interface Props {
		quizData: FlashcardData[];
		isQuizMode: boolean;
		onComplete?: () => void;
	}

	let { quizData = [], isQuizMode = $bindable(), onComplete }: Props = $props();

	let currentIndex = $state(0);
	let isFlipped = $state(false);
	let selectedOption = $state<number | null>(null);
	let randomizedOptions = $state<Option[]>([]);
	let answersStatus = $state<boolean[]>([]); // Track answer status for each card

	const currentCard = $derived(quizData[currentIndex]);
	const isAllAnswered = $derived(answersStatus.every(status => status === true));
	const isAnswered = $derived(answersStatus[currentIndex]);

	function shuffleArray<T>(array: T[]): T[] {
		const newArray = [...array];
		for (let i = newArray.length - 1; i > 0; i--) {
			const j = Math.floor(Math.random() * (i + 1));
			[newArray[i], newArray[j]] = [newArray[j], newArray[i]];
		}
		return newArray;
	}

	function handleStart() {
		isQuizMode = true;
		currentIndex = 0;
		answersStatus = new Array(quizData.length).fill(false);
		resetCardState();
	}

	function resetCardState() {
		isFlipped = false;
		selectedOption = null;
		if (currentCard && currentCard.type === 'mcq' && currentCard.options) {
			randomizedOptions = shuffleArray(currentCard.options);
		}
	}

	function handleFinish() {
		if (isAllAnswered) {
			isQuizMode = false;
			if (onComplete) onComplete();
		}
	}

	function handleFlip() {
		if (currentCard.type === 'flashcard') {
			isFlipped = !isFlipped;
			if (!answersStatus[currentIndex]) {
				answersStatus[currentIndex] = true;
			}
		}
	}

	function handleOptionSelect(index: number) {
		if (isAnswered) return;
		selectedOption = index;
		answersStatus[currentIndex] = true;
	}

	function nextCard() {
		if (currentIndex < quizData.length - 1) {
			currentIndex++;
			resetCardState();
		}
	}

	function prevCard() {
		if (currentIndex > 0) {
			currentIndex--;
			resetCardState();
		}
	}
</script>

<div class="quiz-container">
	{#if !isQuizMode}
		<div class="quiz-start-view">
			<div class="quiz-icon">📝</div>
			<h2>Kuis Interaktif</h2>
			<p>Uji pemahamanmu dengan kuis flashcard dan pilihan ganda ini.</p>
			<div class="alert alert-warning">
				⚠️ <strong>Penting:</strong> Saat kuis dimulai, materi pelajaran di sisi kiri akan disembunyikan agar kamu bisa fokus menjawab.
			</div>
			<button class="btn btn-primary btn-lg" onclick={handleStart}>
				Mulai Kuis Sekarang
			</button>
		</div>
	{:else if quizData.length > 0}
		<div class="quiz-active-view">
			<div class="quiz-progress">
				Pertanyaan {currentIndex + 1} dari {quizData.length}
				<div class="progress-bar-bg">
					<div class="progress-bar-fill" style="width: {((currentIndex + 1) / quizData.length) * 100}%"></div>
				</div>
			</div>

			{#if currentCard.type === 'mcq'}
				<!-- Multiple Choice View -->
				<div class="mcq-view">
					<div class="question-box">
						<div class="side-label">Pertanyaan</div>
						<div class="card-content">
							{@html currentCard.question}
						</div>
					</div>

					<div class="options-grid">
						{#each randomizedOptions as option, i}
							<button 
								class="option-btn" 
								class:selected={selectedOption === i}
								class:correct={isAnswered && option.is_correct}
								class:wrong={isAnswered && selectedOption === i && !option.is_correct}
								onclick={() => handleOptionSelect(i)}
								disabled={isAnswered}
							>
								<div class="option-marker">
									{String.fromCharCode(65 + i)}
								</div>
								<div class="option-text">
									{@html option.text}
								</div>
							</button>
						{/each}
					</div>

					{#if isAnswered}
						<div class="feedback-area" class:correct={randomizedOptions[selectedOption!].is_correct}>
							<div class="feedback-status">
								{#if randomizedOptions[selectedOption!].is_correct}
									🎉 <strong>Benar!</strong> Jawabanmu tepat.
								{:else}
									❌ <strong>Kurang tepat.</strong> Coba pelajari lagi materinya nanti ya.
								{/if}
							</div>
							{#if currentCard.explanation}
								<div class="explanation-box">
									{@html currentCard.explanation}
								</div>
							{/if}
						</div>
					{/if}
				</div>
			{:else}
				<!-- Flashcard View -->
				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="flashcard-wrapper" onclick={handleFlip}>
					<div class="flashcard" class:flipped={isFlipped}>
						<div class="flashcard-front">
							<div class="side-label">Pertanyaan</div>
							<div class="card-content">
								{@html currentCard.front}
							</div>
							<div class="flip-hint">Klik untuk melihat jawaban</div>
						</div>
						<div class="flashcard-back">
							<div class="side-label">Jawaban</div>
							<div class="card-content">
								{@html currentCard.back}
							</div>
							{#if currentCard.explanation}
								<div class="explanation-box small">
									{@html currentCard.explanation}
								</div>
							{/if}
							<div class="flip-hint">Klik untuk kembali ke pertanyaan</div>
						</div>
					</div>
				</div>
			{/if}

			<div class="quiz-controls">
				<button class="btn btn-outline" onclick={prevCard} disabled={currentIndex === 0}>
					← Sebelumnya
				</button>
				
				{#if currentIndex < quizData.length - 1}
					<button class="btn btn-primary" onclick={nextCard} disabled={!isAnswered}>
						Selanjutnya →
					</button>
				{:else}
					<button class="btn btn-success" onclick={handleFinish} disabled={!isAllAnswered}>
						Selesai Kuis
					</button>
				{/if}
			</div>

			<div class="cancel-container">
				<button class="btn-exit-quiz" onclick={handleFinish} disabled={!isAllAnswered}>Batal Kuis</button>
				{#if !isAllAnswered}
					<span class="cancel-lock-hint">🔒 Selesaikan semua pertanyaan untuk dapat keluar</span>
				{/if}
			</div>
		</div>
	{:else}
		<div class="quiz-empty">
			<p>Tidak ada data kuis untuk pelajaran ini.</p>
		</div>
	{/if}
</div>

<style>
	.quiz-container {
		padding: 1.5rem;
		height: 100%;
		display: flex;
		flex-direction: column;
		background: var(--color-bg);
		overflow-y: auto;
	}

	.quiz-active-view {
		flex: 1;
		display: flex;
		flex-direction: column;
	}

	.quiz-start-view {
		text-align: center;
		max-width: 400px;
		margin: auto;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.quiz-icon {
		font-size: 4rem;
		margin-bottom: 0.5rem;
	}

	.alert {
		padding: 1rem;
		border-radius: 8px;
		font-size: 0.9rem;
		line-height: 1.4;
		text-align: left;
	}

	.alert-warning {
		background: #fff9db;
		border: 1px solid #fab005;
		color: #862e00;
	}

	.quiz-progress {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin-bottom: 1.5rem;
	}

	.progress-bar-bg {
		height: 6px;
		background: var(--color-border);
		border-radius: 3px;
		margin-top: 0.5rem;
		overflow: hidden;
	}

	.progress-bar-fill {
		height: 100%;
		background: var(--color-primary, #339af0);
		transition: width 0.3s ease;
	}

	/* MCQ Styling */
	.mcq-view {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		margin-bottom: 2rem;
	}

	.question-box {
		background: white;
		border: 2px solid var(--color-border);
		border-radius: 12px;
		padding: 1.5rem;
	}

	.options-grid {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.option-btn {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 1rem;
		background: white;
		border: 2px solid var(--color-border);
		border-radius: 12px;
		cursor: pointer;
		text-align: left;
		transition: all 0.2s;
		font-size: 1rem;
		color: var(--color-text);
	}

	.option-btn:hover:not(:disabled) {
		border-color: var(--color-primary);
		background: #f1f9ff;
	}

	.option-btn.selected {
		border-color: var(--color-primary);
		background: #e7f5ff;
	}

	.option-btn.correct {
		border-color: #40c057;
		background: #ebfbee;
	}

	.option-btn.wrong {
		border-color: #fa5252;
		background: #fff5f5;
	}

	.option-marker {
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: #f1f3f5;
		border-radius: 8px;
		font-weight: 700;
		font-size: 0.9rem;
		flex-shrink: 0;
	}

	.option-btn.correct .option-marker { background: #40c057; color: white; }
	.option-btn.wrong .option-marker { background: #fa5252; color: white; }

	.option-text {
		flex: 1;
	}

	.feedback-area {
		padding: 1.25rem;
		border-radius: 12px;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.feedback-area.correct { color: #2b8a3e; background: #ebfbee; }
	.feedback-area:not(.correct) { color: #c92a2a; background: #fff5f5; }

	.explanation-box {
		font-size: 0.85rem;
		line-height: 1.5;
		padding: 0.75rem;
		background: rgba(255, 255, 255, 0.5);
		border-radius: 8px;
		text-align: left;
	}

	.explanation-box.small {
		margin-top: 1rem;
		max-width: 100%;
		font-size: 0.75rem;
	}

	.explanation-box :global(p) { margin: 0; }

	/* Flashcard Styling */
	.flashcard-wrapper {
		flex: 1;
		perspective: 1000px;
		min-height: 250px;
		cursor: pointer;
		margin-bottom: 2rem;
	}

	.flashcard {
		position: relative;
		width: 100%;
		height: 100%;
		transition: transform 0.6s cubic-bezier(0.4, 0, 0.2, 1);
		transform-style: preserve-3d;
	}

	.flashcard.flipped {
		transform: rotateY(180deg);
	}

	.flashcard-front, .flashcard-back {
		position: absolute;
		width: 100%;
		height: 100%;
		backface-visibility: hidden;
		display: flex;
		flex-direction: column;
		padding: 2rem;
		background: white;
		border: 2px solid var(--color-border);
		border-radius: 16px;
		box-shadow: 0 4px 12px rgba(0,0,0,0.05);
	}

	.flashcard-back {
		transform: rotateY(180deg);
		background: #f8f9fa;
	}

	.side-label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin-bottom: 1rem;
		font-weight: 700;
	}

	.card-content {
		flex: 1;
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
		text-align: center;
		font-size: 1.25rem;
		color: var(--color-text);
		line-height: 1.5;
	}

	:global(.card-content code) {
		background: #eee;
		padding: 0.2rem 0.4rem;
		border-radius: 4px;
		font-family: monospace;
	}

	:global(.card-content p) {
		margin: 0;
	}

	.flip-hint {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		margin-top: 1rem;
		font-style: italic;
	}

	.quiz-controls {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		margin-top: auto;
	}

	.btn {
		padding: 0.6rem 1.2rem;
		border-radius: 8px;
		font-weight: 600;
		cursor: pointer;
		border: none;
		transition: opacity 0.2s;
	}

	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-primary { background: #339af0; color: white; }
	.btn-success { background: #40c057; color: white; }
	.btn-outline { background: white; border: 1px solid var(--color-border); color: var(--color-text); }
	.btn-lg { padding: 1rem 2rem; font-size: 1.1rem; }

	.btn-exit-quiz {
		background: none;
		border: none;
		color: var(--color-text-muted);
		text-decoration: underline;
		font-size: 0.85rem;
		cursor: pointer;
	}

	.btn-exit-quiz:disabled {
		color: #adb5bd;
		text-decoration: none;
		cursor: not-allowed;
	}

	.cancel-container {
		display: flex;
		flex-direction: column;
		align-items: center;
		margin-top: 1rem;
		gap: 0.5rem;
	}

	.cancel-lock-hint {
		font-size: 0.75rem;
		color: #fa5252;
		font-weight: 500;
	}

	.quiz-empty {
		text-align: center;
		margin: auto;
		color: var(--color-text-muted);
	}

	@media (max-width: 600px) {
		.card-content { font-size: 1.1rem; }
		.option-btn { padding: 0.75rem; font-size: 0.95rem; }
	}
</style>
