<script lang="ts">
	import { tick, mount, unmount } from 'svelte';
	import SlideCarousel from '$components/SlideCarousel.svelte';
	import { highlightAllCode } from '$actions/highlightCode';
	import { renderCircuitEmbeds } from '$actions/renderCircuitEmbeds';
	import { renderFlowchartEmbeds } from '$actions/renderFlowchartEmbeds';
	import { autoRenderMath } from '$lib/actions/renderMath';

	interface Props {
		lessonHtml: string;
		exerciseHtml?: string;
		quizData?: unknown[];
		slides?: string[];
		activeTabs?: string[];
	}

	let { lessonHtml, exerciseHtml = '', quizData = [], slides = [], activeTabs = [] }: Props = $props();

	let contentEl = $state<HTMLElement | null>(null);
	// Plain variable (not $state) to avoid infinite reactivity loops when mounting inside $effect
	let slideComponent: ReturnType<typeof mount> | null = null;

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

<div class="lesson-content-view prose" bind:this={contentEl}>
	{@html lessonHtml}
</div>

<style>
	.lesson-content-view {
		font-size: 1rem;
		line-height: 1.5;
		text-align: left;
		max-width: 70ch;
	}
</style>
