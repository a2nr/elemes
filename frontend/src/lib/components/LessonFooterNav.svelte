<script lang="ts">
	let { prevLesson, nextLesson }: {
		prevLesson?: { filename: string; title: string } | null;
		nextLesson?: { filename: string; title: string } | null;
	} = $props();
</script>

<div class="lesson-footer-nav">
	{#if prevLesson}
		<a href="/lesson/{prevLesson.filename}" class="btn btn-secondary">
			&larr; {prevLesson.title}
		</a>
	{:else}
		<span></span>
	{/if}
	{#if nextLesson}
		<a href="/lesson/{nextLesson.filename}" class="btn btn-primary">
			{nextLesson.title} &rarr;
		</a>
	{/if}
</div>

<style>
	.lesson-footer-nav {
		display: flex;
		justify-content: space-between;
		margin-top: 2rem;
		padding-top: 1rem;
		border-top: 1px solid var(--color-border);
	}
</style>
