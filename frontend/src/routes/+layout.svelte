<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { auth } from '$stores/auth';
	import { theme } from '$stores/theme';
	import Navbar from '$components/Navbar.svelte';
	import Footer from '$components/Footer.svelte';
	import '../app.css';

	let { children } = $props();

	onMount(() => {
		theme.init();
		auth.init();
	});

	// Playground = full-viewport route: tanpa padding/overflow halaman biasa, footer disembunyikan.
	// Navbar tetap tampil (theme toggle + token login) — tinggi main otomatis menyesuaikan via flex.
	let isPlayground = $derived(
		$page.url.pathname === '/playground' || $page.url.pathname.startsWith('/playground/')
	);
</script>

<svelte:head>
	{#if isPlayground}
		<style>
			@media (min-width: 769px) {
				html,
				body {
					height: 100dvh !important;
					max-height: 100dvh !important;
					overflow: hidden !important;
					overscroll-behavior: none !important;
				}
				nav.navbar {
					position: relative !important;
					flex-shrink: 0 !important;
					top: auto !important;
				}
			}
		</style>
	{/if}
</svelte:head>

<Navbar />

{#if isPlayground}
	<main class="playground-main">
		{@render children()}
	</main>
{:else}
	<main class="container" style="flex: 1; padding-block: 1.5rem; overflow: visible;">
		{@render children()}
	</main>
	<Footer />
{/if}

<style>
	.playground-main {
		flex: 1 1 0;
		display: flex;
		flex-direction: column;
		width: 100%;
		max-width: none;
		margin: 0;
		padding: 0;
		min-height: 0;
		overflow: hidden;
	}
</style>
