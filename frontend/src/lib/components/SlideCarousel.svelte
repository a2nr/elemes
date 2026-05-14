<script lang="ts">
	let { slides = [] } = $props<{ slides: string[] }>();

	let activeIndex = $state(0);
	let isFullscreen = $state(false);
	let isExpanded = $state(false); // Default to hidden (collapsed)
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

	function toggleExpand() {
		isExpanded = !isExpanded;
	}

	// Keyboard navigation
	function handleKeydown(e: KeyboardEvent) {
		if (!isExpanded && !isFullscreen) return;
		if (e.key === 'ArrowRight') next();
		if (e.key === 'ArrowLeft') prev();
		if (e.key === 'f' || e.key === 'F') toggleFullscreen();
		if (e.key === 'Escape' && isFullscreen) document.exitFullscreen();
	}

	// Listen for fullscreen change events
	if (typeof document !== 'undefined') {
		document.addEventListener('fullscreenchange', () => {
			isFullscreen = !!document.fullscreenElement;
			if (isFullscreen) isExpanded = true;
		});
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="slide-carousel-wrapper" class:collapsed={!isExpanded && !isFullscreen}>
	{#if !isExpanded && !isFullscreen}
		<button class="expand-toggle-btn" onclick={toggleExpand}>
			<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
			Tampilkan Slide Materi ({slides.length} Slide)
		</button>
	{:else}
		<div class="slide-carousel" class:is-fullscreen={isFullscreen} bind:this={carouselEl}>
			<div class="carousel-header">
				<button class="collapse-btn" onclick={toggleExpand} aria-label="Sembunyikan slide">
					<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>
					Sembunyikan Slide
				</button>
				<div class="slide-counter-top">
					{activeIndex + 1} / {slides.length}
				</div>
			</div>

			<div class="slide-container">
				{#each slides as slide, i}
					<div class="slide" class:active={i === activeIndex}>
						<div class="slide-inner">
							<div class="slide-content prose">
								{@html slide}
							</div>
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
			{/if}
		</div>
	{/if}
</div>

<style>
	:root {
		--slide-bg: #f8fafc;
		--slide-controls-bg: #ffffff;
		--slide-border: #e2e8f0;
		--slide-primary: #3b82f6;
		--slide-text: #1e293b;
		--slide-header-bg: #f1f5f9;
	}

	.slide-carousel-wrapper {
		margin: 1.5rem 0;
		transition: all 0.3s ease;
	}

	.slide-carousel-wrapper.collapsed {
		border: 1px dashed var(--slide-border);
		border-radius: 12px;
		background: var(--slide-bg);
	}

	.expand-toggle-btn {
		width: 100%;
		padding: 1.25rem;
		background: transparent;
		border: none;
		color: #64748b;
		font-weight: 600;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		transition: color 0.2s, background 0.2s;
		border-radius: 12px;
	}

	.expand-toggle-btn:hover {
		color: var(--slide-primary);
		background: rgba(59, 130, 246, 0.05);
	}

	.slide-carousel {
		background: var(--slide-bg);
		border: 1px solid var(--slide-border);
		border-radius: 12px;
		position: relative;
		overflow: hidden;
		box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
		display: flex;
		flex-direction: column;
		color: var(--slide-text);
		height: 500px; /* Slightly taller default */
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

	.carousel-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 1rem;
		background: var(--slide-header-bg);
		border-bottom: 1px solid var(--slide-border);
	}

	.is-fullscreen .carousel-header {
		display: none; /* Hide top header in fullscreen */
	}

	.collapse-btn {
		background: transparent;
		border: none;
		color: #64748b;
		font-size: 0.85rem;
		font-weight: 600;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		padding: 0.25rem 0.5rem;
		border-radius: 6px;
	}

	.collapse-btn:hover {
		background: rgba(0,0,0,0.05);
		color: var(--slide-text);
	}

	.slide-counter-top {
		font-size: 0.75rem;
		font-weight: 700;
		color: #94a3b8;
		background: white;
		padding: 2px 8px;
		border-radius: 10px;
		border: 1px solid var(--slide-border);
	}

	.slide-container {
		display: grid;
		grid-template-areas: "stack";
		flex: 1;
		min-height: 0;
		background: inherit;
	}

	.slide {
		grid-area: stack;
		opacity: 0;
		visibility: hidden;
		transition: opacity 0.4s ease, transform 0.4s ease;
		transform: translateX(20px);
		display: flex;
		flex-direction: column;
		background: inherit;
		overflow-y: auto;
		height: 100%;
		scrollbar-width: thin;
	}

	.slide.active {
		opacity: 1;
		visibility: visible;
		transform: translateX(0);
	}

	.slide-inner {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: clamp(1rem, 5vw, 3rem);
		min-height: 100%;
		width: 100%;
		box-sizing: border-box;
		text-align: center;
	}

	.slide-inner::before,
	.slide-inner::after {
		content: "";
		margin: auto;
	}

	.slide-content {
		max-width: 1000px !important; 
		font-size: clamp(0.95rem, 1.5vw, 1.25rem);
	}

	.slide-content :global(h1) { font-size: clamp(1.8rem, 5vw, 3rem); line-height: 1.2; margin-top: 0; }
	.slide-content :global(h2) { font-size: clamp(1.5rem, 4vw, 2.25rem); }
	.slide-content :global(h3) { font-size: clamp(1.2rem, 3vw, 1.75rem); }
	.slide-content :global(p) { line-height: 1.6; }
	.slide-content :global(img) { 
		max-height: 50vh; 
		width: auto; 
		max-width: 100%;
		object-fit: contain;
		border-radius: 8px;
		margin: 1rem auto;
	}

	.is-fullscreen .slide-inner {
		padding: clamp(1.5rem, 8vw, 6rem);
	}

	.is-fullscreen .slide-content {
		font-size: clamp(1.1rem, 2vw, 1.6rem);
	}

	.is-fullscreen .slide-content :global(h1) { font-size: clamp(2.5rem, 8vw, 5rem); }
	.is-fullscreen .slide-content :global(h2) { font-size: clamp(2rem, 6vw, 3.5rem); }
	.is-fullscreen .slide-content :global(h3) { font-size: clamp(1.5rem, 4vw, 2.5rem); }

	.slide-controls {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.75rem 1.25rem;
		background: var(--slide-controls-bg);
		border-top: 1px solid var(--slide-border);
		user-select: none;
		z-index: 10;
	}

	.is-fullscreen .slide-controls {
		padding: 1.5rem 3rem;
		background: var(--slide-bg);
	}

	.left-controls, .right-controls {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}

	.btn-nav, .btn-fullscreen {
		background: var(--slide-primary);
		color: white;
		border: none;
		border-radius: 10px;
		width: 44px;
		height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		font-size: 1.25rem;
		transition: all 0.2s;
		box-shadow: 0 2px 4px rgba(0,0,0,0.1);
	}

	.btn-fullscreen {
		background: #64748b;
	}

	.btn-nav:hover:not(:disabled), .btn-fullscreen:hover {
		filter: brightness(1.1);
		transform: translateY(-2px);
		box-shadow: 0 4px 8px rgba(0,0,0,0.15);
	}

	.btn-nav:active:not(:disabled), .btn-fullscreen:active {
		transform: translateY(0);
	}

	.btn-nav:disabled {
		background: #cbd5e1;
		cursor: not-allowed;
		box-shadow: none;
	}

	.slide-dots {
		display: flex;
		gap: 0.6rem;
	}

	.dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: #cbd5e1;
		border: none;
		padding: 0;
		cursor: pointer;
		transition: all 0.2s;
	}

	.dot.active {
		background: var(--slide-primary);
		transform: scale(1.3);
		width: 24px;
		border-radius: 5px;
	}

	/* Desktop Counter moved to controls if not fullscreen */
	:not(.is-fullscreen) .slide-counter-bottom {
		font-size: 0.85rem;
		font-weight: 600;
		color: #64748b;
	}

	/* Mobile Optimizations */
	@media (max-width: 768px) {
		.slide-carousel {
			height: auto;
			min-height: 400px;
		}
		
		.slide-inner {
			padding: 1.5rem 1rem;
		}

		.slide-controls {
			padding: 0.75rem;
		}

		.btn-nav, .btn-fullscreen {
			width: 40px;
			height: 40px;
		}

		.slide-dots {
			display: none;
		}
	}

	/* Landscape specific fixes */
	@media (max-height: 500px) and (orientation: landscape) {
		.is-fullscreen .slide-inner {
			padding: 1rem 3rem;
			display: block;
			text-align: left;
		}

		.is-fullscreen .slide-inner::before,
		.is-fullscreen .slide-inner::after {
			display: none;
		}

		.is-fullscreen .slide-content :global(h1) { font-size: 2rem; }
		.is-fullscreen .slide-content :global(img) { max-height: 60vh; width: auto; float: right; margin: 0 0 1rem 1.5rem; }

		.is-fullscreen .slide-controls {
			padding: 0.5rem 2rem;
		}

		.btn-nav, .btn-fullscreen {
			height: 36px;
			width: 36px;
		}
	}
</style>
