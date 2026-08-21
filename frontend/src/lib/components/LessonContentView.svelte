<script lang="ts">
	import { tick } from 'svelte';
	import { highlightAllCode } from '$actions/highlightCode';
	import { renderCircuitEmbeds } from '$actions/renderCircuitEmbeds';
	import { renderFlowchartEmbeds } from '$actions/renderFlowchartEmbeds';
	import { renderMath, autoRenderMath } from '$lib/actions/renderMath';

	interface Props {
		lessonHtml: string;
		exerciseHtml?: string;
		quizData?: unknown[];
		slides?: string[];
		activeTabs?: string[];
	}

	let { lessonHtml, exerciseHtml = '', quizData = [], slides = [], activeTabs = [] }: Props = $props();

	let contentEl = $state<HTMLElement | null>(null);

	$effect(() => {
		if (contentEl && lessonHtml) {
			tick().then(() => {
				if (!contentEl) return;
				highlightAllCode(contentEl);
				renderCircuitEmbeds(contentEl);
				renderFlowchartEmbeds(contentEl);
				autoRenderMath(contentEl);
			});
		}
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
