<script lang="ts">
	import { onMount } from 'svelte';
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
</script>

<Navbar />

<main class="container" style="flex: 1; padding-block: 1.5rem;">
	{@render children()}
</main>

<Footer />
