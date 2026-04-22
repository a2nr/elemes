<script lang="ts">
	import LessonCard from '$components/LessonCard.svelte';
	import { env } from '$env/dynamic/public';

	let { data } = $props();
</script>

<svelte:head>
	<title>{env.PUBLIC_PAGE_TITLE_SUFFIX || 'Elemes LMS'}</title>
</svelte:head>

{#if data.homeContent}
	<section class="home-intro">
		{@html data.homeContent}
	</section>
{/if}

{#if data.lessons.length === 0}
	<p class="empty">Belum ada pelajaran yang tersedia.</p>
{:else}
	<section class="lesson-grid">
		{#each data.lessons as lesson (lesson.filename)}
			<LessonCard {lesson} />
		{/each}
	</section>
{/if}

<style>
	.home-intro {
		margin-bottom: 2rem;
	}
	.home-intro :global(ul),
	.home-intro :global(ol) {
		padding-left: 1.5rem;
		margin-bottom: 0.75rem;
	}
	.home-intro :global(li) {
		margin-bottom: 0.25rem;
	}
	.lesson-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 1rem;
	}
	.empty {
		text-align: center;
		padding: 3rem;
		color: var(--color-text-muted);
	}
</style>
