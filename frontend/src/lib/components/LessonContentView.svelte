<script lang="ts">
	import { tick, mount, unmount } from 'svelte';
	import SlideCarousel from '$components/SlideCarousel.svelte';
	import { highlightAllCode } from '$actions/highlightCode';
	import { renderCircuitEmbeds } from '$actions/renderCircuitEmbeds';
	import { renderFlowchartEmbeds } from '$actions/renderFlowchartEmbeds';
	import { autoRenderMath } from '$lib/actions/renderMath';

	export interface ClickTextDetail {
		word: string;
		snippet: string;
		blockText: string;
		blockIndex: number;
		totalBlocks: number;
		event: MouseEvent;
	}

	interface Props {
		lessonHtml: string;
		exerciseHtml?: string;
		quizData?: unknown[];
		slides?: string[];
		activeTabs?: string[];
		clickable?: boolean;
		onclicktext?: (detail: ClickTextDetail) => void;
	}

	let {
		lessonHtml,
		exerciseHtml = '',
		quizData = [],
		slides = [],
		activeTabs = [],
		clickable = false,
		onclicktext
	}: Props = $props();

	let contentEl = $state<HTMLElement | null>(null);
	// Plain variable (not $state) to avoid infinite reactivity loops when mounting inside $effect
	let slideComponent: ReturnType<typeof mount> | null = null;

	function handleContentClick(event: MouseEvent) {
		if (!clickable || !onclicktext) return;

		// Don't trigger when clicking buttons, links, controls, or interactive embeds
		const targetEl = event.target as HTMLElement | null;
		if (targetEl?.closest('button, a, input, select, textarea, .try-btn, iframe, [data-interactive]')) {
			return;
		}

		let textNode: Node | null = null;
		let offset = 0;

		const doc = document as any;
		if (doc.caretPositionFromPoint) {
			const pos = doc.caretPositionFromPoint(event.clientX, event.clientY);
			if (pos) {
				textNode = pos.offsetNode;
				offset = pos.offset;
			}
		} else if (doc.caretRangeFromPoint) {
			const range = doc.caretRangeFromPoint(event.clientX, event.clientY);
			if (range) {
				textNode = range.startContainer;
				offset = range.startOffset;
			}
		}

		let word = '';
		let snippet = '';
		if (textNode) {
			const fullText = textNode.textContent || '';
			let start = offset;
			while (start > 0 && /\S/.test(fullText[start - 1])) {
				start--;
			}
			let end = offset;
			while (end < fullText.length && /\S/.test(fullText[end])) {
				end++;
			}
			word = fullText.slice(start, end).trim();
			const snippetStart = Math.max(0, start - 25);
			const snippetEnd = Math.min(fullText.length, end + 25);
			snippet = fullText.slice(snippetStart, snippetEnd).trim();
		}

		let blockEl: Element | null = null;
		let curr: Node | null = textNode || targetEl;
		while (curr && curr !== contentEl) {
			if (curr.nodeType === Node.ELEMENT_NODE) {
				const tag = (curr as Element).tagName.toLowerCase();
				if (['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'pre', 'tr', 'td', 'th', 'summary'].includes(tag)) {
					blockEl = curr as Element;
					break;
				}
			}
			curr = curr.parentNode;
		}

		const blockText = blockEl ? (blockEl.textContent || '').trim() : '';
		let blockIndex = -1;
		let totalBlocks = 0;
		if (blockEl && contentEl) {
			const allBlocks = contentEl.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, blockquote, pre, tr');
			totalBlocks = allBlocks.length;
			blockIndex = Array.from(allBlocks).indexOf(blockEl);
		}

		onclicktext({
			word,
			snippet,
			blockText,
			blockIndex,
			totalBlocks,
			event
		});
	}

	$effect(() => {
		if (contentEl && lessonHtml) {
			const currentSlides = slides;
			const currentContentEl = contentEl;

			tick().then(() => {
				if (!currentContentEl) return;

				if (slideComponent) {
					try {
						unmount(slideComponent);
					} catch (e) {
						// Ignore unmount error if DOM element was already disposed
					}
					slideComponent = null;
				}

				if (currentSlides && currentSlides.length > 0) {
					const mountPoint = currentContentEl.querySelector('#slide-mount-point');
					if (mountPoint) {
						mountPoint.innerHTML = '';
						try {
							slideComponent = mount(SlideCarousel, {
								target: mountPoint,
								props: { slides: currentSlides }
							});
						} catch (e) {
							console.error('Failed to mount SlideCarousel in LessonContentView:', e);
						}
					}
				}

				highlightAllCode(currentContentEl);
				renderCircuitEmbeds(currentContentEl);
				renderFlowchartEmbeds(currentContentEl);
				autoRenderMath(currentContentEl);
			});
		}

		return () => {
			if (slideComponent) {
				try {
					unmount(slideComponent);
				} catch (e) {
					// Ignore
				}
				slideComponent = null;
			}
		};
	});
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="lesson-content-view prose"
	class:clickable
	bind:this={contentEl}
	onclick={handleContentClick}
>
	{@html lessonHtml}
</div>

<style>
	.lesson-content-view {
		font-size: 1rem;
		line-height: 1.5;
		text-align: left;
		max-width: 70ch;
	}
	.lesson-content-view.clickable {
		cursor: text;
	}
	/* Match /lesson .prose typography (lesson.css) */
	.lesson-content-view p {
		margin-bottom: 1.5rem;
	}
	.lesson-content-view h2 {
		font-size: 1.5rem;
		margin-top: 3rem;
		margin-bottom: 1.5rem;
	}
	.lesson-content-view h3 {
		font-size: 1.25rem;
		margin-top: 2rem;
		margin-bottom: 1rem;
	}
	.lesson-content-view pre {
		background: var(--color-bg-secondary);
		padding: 0.75rem;
		border-radius: var(--radius);
		overflow-x: auto;
		position: relative;
	}
</style>
