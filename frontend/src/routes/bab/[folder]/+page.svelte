<script lang="ts">
	import LessonCard from '$components/LessonCard.svelte';
	import { env } from '$env/dynamic/public';
	import { renderMath } from '$lib/actions/renderMath';
	
	export let data: {
		title: string;
		introHtml: string;
		lessons: import('$types/lesson').Lesson[];
		folder: string;
	};
</script>

<svelte:head>
	<title>{data.title || env.PUBLIC_PAGE_TITLE_SUFFIX || 'Elemes LMS'}</title>
</svelte:head>

<section class="bab-page">
	{#if data.introHtml}
		<section class="intro" use:renderMath>
			{@html data.introHtml}
		</section>
	{/if}
	
	{#if data.lessons.length === 0}
		<p class="empty">Belum ada pelajaran yang ditemukan untuk bab ini.</p>
	{:else}
		<section class="lesson-grid">
			{#each data.lessons as lesson (lesson.filename)}
				<LessonCard {lesson} />
			{/each}
		</section>
	{/if}
</section>

<style>
	.bab-page {
		max-width: 800px;
		margin: 0 auto;
		padding: 1rem;
	}
	.intro {
		margin-bottom: 2rem;
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