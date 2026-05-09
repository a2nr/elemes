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
		completedStatus?: string; // e.g. "5/6" or "completed"
		onComplete?: (status: string) => void;
	}

	let { quizData = [], isQuizMode = $bindable(), completedStatus = '', onComplete }: Props = $props();

	let currentIndex = $state(0);
	let isFlipped = $state(false);
	let selectedOption = $state<number | null>(null);
	let randomizedOptions = $state<Option[]>([]);
	let answersStatus = $state<boolean[]>([]); // Track if answered/flipped
	let userSelections = $state<(number | null)[]>([]); // Track user choice index for MCQ
	let showSummary = $state(false);

	const currentCard = $derived(quizData[currentIndex]);
	const isAllAnswered = $derived(answersStatus.every(status => status === true));
	const isAnswered = $derived(answersStatus[currentIndex]);
	
	// Summary data
	const correctCount = $derived(
		quizData.reduce((acc, card, i) => {
			if (card.type === 'mcq' && userSelections[i] !== null) {
				const opts = card.options || [];
				// Note: this uses original quizData order, but userSelections matches it
				// Wait, if options are randomized, we need to store the correct status
				// Actually, randomizedOptions is per-card, so we should store if they got it right
			}
			return acc;
		}, 0)
	);

	// Better way: Track correctness directly
	let isCorrectArray = $state<boolean[]>([]);

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
		userSelections = new Array(quizData.length).fill(null);
		isCorrectArray = new Array(quizData.length).fill(false);
		showSummary = false;
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
		if (!isAllAnswered) return;

		if (window.confirm("Apakah anda yakin untuk menyelesaikan kuis? Materi akan muncul kembali setelah ini.")) {
			const mcqTotal = quizData.filter(c => c.type === 'mcq').length;
			const correctTotal = isCorrectArray.filter((v, i) => quizData[i].type === 'mcq' && v).length;
			
			// If it's pure flashcards, just 'completed'. Otherwise 'correct/total'
			const statusString = mcqTotal > 0 ? `${correctTotal}/${mcqTotal}` : 'completed';
			
			const passThreshold = 0.75;
			const score = mcqTotal > 0 ? correctTotal / mcqTotal : 1.0;

			// Send to backend
			if (onComplete) onComplete(statusString);
			
			// Show local summary
			showSummary = true;
			isQuizMode = false;
		}
	}

	function handleFlip() {
		if (currentCard.type === 'flashcard') {
			isFlipped = !isFlipped;
			if (!answersStatus[currentIndex]) {
				answersStatus[currentIndex] = true;
				isCorrectArray[currentIndex] = true; // Flashcards are always "correct" once seen
			}
		}
	}

	function handleOptionSelect(index: number) {
		if (isAnswered) return;
		selectedOption = index;
		answersStatus[currentIndex] = true;
		userSelections[currentIndex] = index;
		isCorrectArray[currentIndex] = randomizedOptions[index].is_correct;
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

	// Determine wrong questions for summary
	const wrongQuestions = $derived(
		quizData.map((card, i) => ({ card, i }))
			.filter(({ card, i }) => card.type === 'mcq' && !isCorrectArray[i])
	);
</script>

<div class="quiz-container">
	{#if showSummary || (completedStatus && completedStatus !== 'not_started' && !isQuizMode)}
		<div class="summary-view">
			<div class="summary-header">
				<div class="summary-icon">🏁</div>
				<h2>Kuis Selesai!</h2>
				{#if completedStatus && !showSummary}
					<p class="score-display">Nilai Anda: <strong>{completedStatus}</strong></p>
					<div class="alert alert-info">
						Kuis ini sudah diselesaikan. Silakan hubungi guru jika ingin mengulang.
					</div>
				{:else}
					{@const mcqTotal = quizData.filter(c => c.type === 'mcq').length}
					{@const correctTotal = isCorrectArray.filter((v, i) => quizData[i].type === 'mcq' && v).length}
					<p class="score-display">Skor: <strong>{correctTotal} / {mcqTotal}</strong></p>
					
					{#if mcqTotal > 0 && (correctTotal / mcqTotal) < 0.75}
						<div class="alert alert-warning">
							Nilai Anda di bawah ambang batas 75%. Pelajari kembali topik di bawah ini.
						</div>
					{:else}
						<div class="alert alert-success">
							Selamat! Anda telah memahami materi ini dengan baik.
						</div>
					{/if}

					{#if wrongQuestions.length > 0}
						<div class="wrong-topics">
							<h3>Topik yang perlu dipelajari lagi:</h3>
							<ul>
								{#each wrongQuestions as { card }}
									<li>{@html card.question}</li>
								{/each}
							</ul>
						</div>
					{/if}
				{/if}
			</div>
		</div>
	{:else if !isQuizMode}
		<div class="quiz-start-view">
			<div class="quiz-icon">📝</div>
			<h2>Kuis Interaktif</h2>
			<p>Uji pemahamanmu dengan kuis ini.</p>
			<div class="alert alert-warning">
				⚠️ <strong>Penting:</strong> Materi pelajaran akan disembunyikan. Kamu harus menjawab semua soal untuk dapat menyelesaikannya.
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
								<div class="option-marker">{String.fromCharCode(65 + i)}</div>
								<div class="option-text">{@html option.text}</div>
							</button>
						{/each}
					</div>

					{#if isAnswered}
						<div class="feedback-area" class:correct={isCorrectArray[currentIndex]}>
							<div class="feedback-status">
								{#if isCorrectArray[currentIndex]}
									🎉 <strong>Benar!</strong>
								{:else}
									❌ <strong>Kurang tepat.</strong>
								{/if}
							</div>
							{#if currentCard.explanation}
								<div class="explanation-box">{@html currentCard.explanation}</div>
							{/if}
						</div>
					{/if}
				</div>
			{:else}
				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="flashcard-wrapper" onclick={handleFlip}>
					<div class="flashcard" class:flipped={isFlipped}>
						<div class="flashcard-front">
							<div class="side-label">Pertanyaan</div>
							<div class="card-content">{@html currentCard.front}</div>
							<div class="flip-hint">Klik untuk melihat jawaban</div>
						</div>
						<div class="flashcard-back">
							<div class="side-label">Jawaban</div>
							<div class="card-content">{@html currentCard.back}</div>
							{#if currentCard.explanation}
								<div class="explanation-box small">{@html currentCard.explanation}</div>
							{/if}
							<div class="flip-hint">Klik untuk kembali ke pertanyaan</div>
						</div>
					</div>
				</div>
			{/if}

			<div class="quiz-controls">
				<button class="btn btn-outline" onclick={prevCard} disabled={currentIndex === 0}>← Sebelumnya</button>
				{#if currentIndex < quizData.length - 1}
					<button class="btn btn-primary" onclick={nextCard} disabled={!isAnswered}>Selanjutnya →</button>
				{:else}
					<button class="btn btn-success" onclick={handleFinish} disabled={!isAllAnswered}>Selesai Kuis</button>
				{/if}
			</div>

			<div class="cancel-container">
				<button class="btn-exit-quiz" disabled>Batal Kuis</button>
				<span class="cancel-lock-hint">🔒 Selesaikan kuis untuk melihat materi kembali</span>
			</div>
		</div>
	{:else}
		<div class="quiz-empty"><p>Tidak ada data kuis.</p></div>
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

	.summary-view {
		text-align: center;
		padding: 2rem 1rem;
		max-width: 500px;
		margin: auto;
	}
	.summary-icon { font-size: 4rem; margin-bottom: 1rem; }
	.score-display { font-size: 1.5rem; margin-bottom: 1.5rem; }
	.score-display strong { color: var(--color-primary); font-size: 2.5rem; }

	.wrong-topics {
		text-align: left;
		margin-top: 2rem;
		padding-top: 2rem;
		border-top: 1px solid var(--color-border);
	}
	.wrong-topics h3 { font-size: 1rem; margin-bottom: 1rem; color: var(--color-danger); }
	.wrong-topics ul { padding-left: 1.5rem; }
	.wrong-topics li { margin-bottom: 0.75rem; font-size: 0.9rem; }

	.quiz-active-view { flex: 1; display: flex; flex-direction: column; }
	.quiz-start-view { text-align: center; max-width: 400px; margin: auto; display: flex; flex-direction: column; gap: 1rem; }
	.quiz-icon { font-size: 4rem; margin-bottom: 0.5rem; }

	.alert { padding: 1rem; border-radius: 8px; font-size: 0.9rem; line-height: 1.4; text-align: left; }
	.alert-warning { background: var(--color-bg-secondary); border: 1px solid var(--color-warning); color: var(--color-text); }
	.alert-success { background: rgba(25, 135, 84, 0.1); border: 1px solid var(--color-success); color: var(--color-success); }
	.alert-info { background: rgba(13, 110, 253, 0.1); border: 1px solid var(--color-primary); color: var(--color-primary); }

	.quiz-progress { font-size: 0.85rem; color: var(--color-text-muted); margin-bottom: 1.5rem; }
	.progress-bar-bg { height: 6px; background: var(--color-border); border-radius: 3px; margin-top: 0.5rem; overflow: hidden; }
	.progress-bar-fill { height: 100%; background: var(--color-primary, #339af0); transition: width 0.3s ease; }

	.mcq-view { flex: 1; display: flex; flex-direction: column; gap: 1.5rem; margin-bottom: 2rem; }
	.question-box { background: var(--color-bg-secondary); border: 2px solid var(--color-border); border-radius: 12px; padding: 1.5rem; }
	.options-grid { display: flex; flex-direction: column; gap: 0.75rem; }
	.option-btn { display: flex; align-items: center; gap: 1rem; padding: 1rem; background: var(--color-bg); border: 2px solid var(--color-border); border-radius: 12px; cursor: pointer; text-align: left; transition: all 0.2s; font-size: 1rem; color: var(--color-text); }
	.option-btn:hover:not(:disabled) { border-color: var(--color-primary); background: var(--color-bg-secondary); }
	.option-btn.selected { border-color: var(--color-primary); background: var(--color-bg-secondary); }
	.option-btn.correct { border-color: var(--color-success); background: rgba(25, 135, 84, 0.15); }
	.option-btn.wrong { border-color: var(--color-danger); background: rgba(220, 53, 69, 0.15); }
	.option-marker { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 8px; font-weight: 700; font-size: 0.9rem; flex-shrink: 0; color: var(--color-text); }
	.option-btn.correct .option-marker { background: var(--color-success); border-color: var(--color-success); color: white; }
	.option-btn.wrong .option-marker { background: var(--color-danger); border-color: var(--color-danger); color: white; }
	.option-text { flex: 1; }

	.feedback-area { padding: 1.25rem; border-radius: 12px; display: flex; flex-direction: column; gap: 0.75rem; }
	.feedback-area.correct { color: var(--color-success); background: rgba(25, 135, 84, 0.1); border: 1px solid rgba(25, 135, 84, 0.2); }
	.feedback-area:not(.correct) { color: var(--color-danger); background: rgba(220, 53, 69, 0.1); border: 1px solid rgba(220, 53, 69, 0.2); }
	.explanation-box { font-size: 0.85rem; line-height: 1.5; padding: 1rem; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 8px; text-align: left; }
	.explanation-box.small { margin-top: 1rem; max-width: 100%; font-size: 0.75rem; }
	.explanation-box :global(p) { margin: 0; }

	.flashcard-wrapper { flex: 1; perspective: 1000px; min-height: 250px; cursor: pointer; margin-bottom: 2rem; }
	.flashcard { position: relative; width: 100%; height: 100%; transition: transform 0.6s cubic-bezier(0.4, 0, 0.2, 1); transform-style: preserve-3d; }
	.flashcard.flipped { transform: rotateY(180deg); }
	.flashcard-front, .flashcard-back { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; flex-direction: column; padding: 2rem; background: var(--color-bg-secondary); border: 2px solid var(--color-border); border-radius: 16px; box-shadow: var(--shadow); }
	.flashcard-back { transform: rotateY(180deg); background: var(--color-bg); }
	.side-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-muted); margin-bottom: 1rem; font-weight: 700; border-bottom: 1px solid var(--color-border); padding-bottom: 0.5rem; }
	.card-content { flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; font-size: 1.25rem; color: var(--color-text); line-height: 1.5; }
	:global(.card-content code) { background: var(--color-bg); border: 1px solid var(--color-border); padding: 0.2rem 0.4rem; border-radius: 4px; font-family: var(--font-mono); }
	:global(.card-content p) { margin: 0; }
	.flip-hint { font-size: 0.75rem; color: var(--color-text-muted); margin-top: 1rem; font-style: italic; }

	.quiz-controls { 
		display: flex; 
		justify-content: space-between; 
		gap: 1rem; 
		margin-top: auto; 
		position: relative;
		z-index: 10; /* Ensure buttons are clickable */
		background: var(--color-bg); /* Prevents card content from showing through during scroll */
		padding-top: 1rem;
	}
	.btn { padding: 0.6rem 1.2rem; border-radius: 8px; font-weight: 600; cursor: pointer; border: none; transition: opacity 0.2s; }
	.btn:disabled { opacity: 0.5; cursor: not-allowed; }
	.btn-primary { background: #339af0; color: white; }
	.btn-success { background: #40c057; color: white; }
	.btn-outline { background: white; border: 1px solid var(--color-border); color: var(--color-text); }
	.btn-lg { padding: 1rem 2rem; font-size: 1.1rem; }

	.btn-exit-quiz { background: none; border: none; color: var(--color-text-muted); text-decoration: underline; font-size: 0.85rem; cursor: pointer; }
	.cancel-container { display: flex; flex-direction: column; align-items: center; margin-top: 1rem; gap: 0.5rem; }
	.cancel-lock-hint { font-size: 0.75rem; color: #fa5252; font-weight: 500; }
	.quiz-empty { text-align: center; margin: auto; color: var(--color-text-muted); }
	@media (max-width: 600px) { .card-content { font-size: 1.1rem; } .option-btn { padding: 0.75rem; font-size: 0.95rem; } }
</style>
