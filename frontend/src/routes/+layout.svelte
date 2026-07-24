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

	// Suppress Navbar/Footer on full-viewport routes (e.g. /playground)
	let isFullViewport = $derived($page.url.pathname === '/playground');
</script>

{#if !isFullViewport}
	<Navbar />
{/if}

<main class="container" style="flex: 1; padding-block: {isFullViewport ? '0' : '1.5rem'}; overflow: {isFullViewport ? 'hidden' : 'visible'}; max-width: {isFullViewport ? '100%' : ''}; padding-inline: {isFullViewport ? '0' : ''}; width: {isFullViewport ? '100%' : ''};">
	{@render children()}
</main>

{#if !isFullViewport}
	<Footer />
{/if}
