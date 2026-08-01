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
	let isPlayground = $derived($page.url.pathname === '/playground');
</script>

<Navbar />

<main class="container" style="flex: 1; padding-block: {isPlayground ? '0' : '1.5rem'}; overflow: {isPlayground ? 'hidden' : 'visible'};">
	{@render children()}
</main>

{#if !isPlayground}
	<Footer />
{/if}
