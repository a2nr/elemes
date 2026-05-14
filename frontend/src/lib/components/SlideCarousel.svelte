<script lang="ts">
	let { slides = [] } = $props<{ slides: string[] }>();

	let activeIndex = $state(0);
	let isFullscreen = $state(false);
	let carouselEl = $state<HTMLElement | null>(null);

	function next() {
		if (activeIndex < slides.length - 1) {
			activeIndex++;
		}
	}

	function prev() {
		if (activeIndex > 0) {
			activeIndex--;
		}
	}

	function goTo(index: number) {
		activeIndex = index;
	}

	function toggleFullscreen() {
		if (!carouselEl) return;

		if (!document.fullscreenElement) {
			carouselEl.requestFullscreen().catch(err => {
				console.error(`Error attempting to enable full-screen mode: ${err.message}`);
			});
		} else {
			document.exitFullscreen();
		}
	}

	// Keyboard navigation
	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowRight') next();
		if (e.key === 'ArrowLeft') prev();
		if (e.key === 'f' || e.key === 'F') toggleFullscreen();
		if (e.key === 'Escape' && isFullscreen) document.exitFullscreen();
	}

	// Listen for fullscreen change events
	if (typeof document !== 'undefined') {
		document.addEventListener('fullscreenchange', () => {
			isFullscreen = !!document.fullscreenElement;
		});
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="slide-carousel" class:is-fullscreen={isFullscreen} bind:this={carouselEl}>
	<div class="slide-container">
		{#each slides as slide, i}
			<div class="slide" class:active={i === activeIndex}>
				<div class="slide-content prose">
					{@html slide}
				</div>
			</div>
		{/each}
	</div>

	{#if slides.length > 0}
		<div class="slide-controls">
			<div class="left-controls">
				<button class="btn-nav prev" onclick={prev} disabled={activeIndex === 0} aria-label="Previous slide">
					&larr;
				</button>
			</div>
			
			<div class="center-controls">
				{#if slides.length > 1}
					<div class="slide-dots">
						{#each slides as _, i}
							<button 
								class="dot" 
								class:active={i === activeIndex} 
								onclick={() => goTo(i)}
								aria-label="Go to slide {i + 1}"
							></button>
						{/each}
					</div>
				{/if}
			</div>

			<div class="right-controls">
				<button class="btn-fullscreen" onclick={toggleFullscreen} aria-label="Toggle fullscreen">
					{#if isFullscreen}
						<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/></svg>
					{:else}
						<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>
					{/if}
				</button>
				<button class="btn-nav next" onclick={next} disabled={activeIndex === slides.length - 1} aria-label="Next slide">
					&rarr;
				</button>
			</div>
		</div>
		<div class="slide-counter">
			{activeIndex + 1} / {slides.length}
		</div>
	{/if}
</div>

<style>
	.slide-carousel {
		background: #f8fafc;
		border: 1px solid #e2e8f0;
		border-radius: 12px;
		margin: 1.5rem 0;
		position: relative;
		overflow: hidden;
		box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
		display: flex;
		flex-direction: column;
	}

	.slide-carousel.is-fullscreen {
		position: fixed;
		top: 0;
		left: 0;
		width: 100vw;
		height: 100vh;
		z-index: 9999;
		margin: 0;
		border-radius: 0;
		background: #ffffff;
	}

	.slide-container {
		display: grid;
		grid-template-areas: "stack";
		flex-grow: 1;
		min-height: 300px;
		background: inherit;
	}

	.is-fullscreen .slide-container {
		min-height: 0;
	}

	.slide {
		grid-area: stack;
		opacity: 0;
		visibility: hidden;
		transition: opacity 0.4s ease, transform 0.4s ease;
		transform: translateX(20px);
		padding: 2.5rem;
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
		text-align: center;
		background: inherit;
		overflow-y: auto;
	}

	.is-fullscreen .slide {
		padding: 4rem;
	}

	.slide.active {
		opacity: 1;
		visibility: visible;
		transform: translateX(0);
	}

	.slide-content {
		max-width: 100%;
		width: 100%;
	}

	.is-fullscreen .slide-content {
		font-size: 1.5rem;
		max-width: 900px;
	}

	.is-fullscreen .slide-content :global(h1) { font-size: 3.5rem; }
	.is-fullscreen .slide-content :global(h2) { font-size: 2.5rem; }
	.is-fullscreen .slide-content :global(h3) { font-size: 2rem; }

	.slide-content :global(h1), 
	.slide-content :global(h2), 
	.slide-content :global(h3), 
	.slide-content :global(p) {
		margin-left: auto;
		margin-right: auto;
	}

	.slide-controls {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem 1.5rem;
		background: #ffffff;
		border-top: 1px solid #e2e8f0;
		user-select: none;
	}

	.is-fullscreen .slide-controls {
		padding: 1.5rem 3rem;
		background: #f8fafc;
	}

	.left-controls, .right-controls {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}

	.btn-nav, .btn-fullscreen {
		background: #3b82f6;
		color: white;
		border: none;
		border-radius: 8px;
		width: 44px;
		height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		font-size: 1.25rem;
		transition: all 0.2s;
	}

	.btn-fullscreen {
		background: #64748b;
	}

	.btn-nav:hover:not(:disabled), .btn-fullscreen:hover {
		filter: brightness(1.1);
		transform: translateY(-1px);
	}

	.btn-nav:active:not(:disabled), .btn-fullscreen:active {
		transform: translateY(0);
	}

	.btn-nav:disabled {
		background: #cbd5e1;
		cursor: not-allowed;
	}

	.slide-dots {
		display: flex;
		gap: 0.5rem;
	}

	.dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: #cbd5e1;
		border: none;
		padding: 0;
		cursor: pointer;
		transition: background 0.2s, transform 0.2s;
	}

	.dot.active {
		background: #3b82f6;
		transform: scale(1.2);
	}

	.slide-counter {
		position: absolute;
		top: 1rem;
		right: 1rem;
		background: rgba(0, 0, 0, 0.05);
		padding: 0.25rem 0.75rem;
		border-radius: 20px;
		font-size: 0.875rem;
		color: #64748b;
		font-weight: 500;
	}

	.is-fullscreen .slide-counter {
		top: 2rem;
		right: 2rem;
		font-size: 1.1rem;
		padding: 0.5rem 1rem;
	}

	@media (max-width: 768px) {
		.slide {
			padding: 1.5rem;
		}
		
		.slide-container {
			min-height: 250px;
		}

		.is-fullscreen .slide {
			padding: 2rem 1rem;
		}
	}
</style>
