<script lang="ts">
	import { auth, authLoggedIn, authStudentName } from '$stores/auth';
	import { theme, themeDark } from '$stores/theme';

	let showLoginModal = $state(false);
	let tokenInput = $state('');
	let loginError = $state('');
	let loading = $state(false);

	async function handleLogin() {
		if (!tokenInput.trim()) return;
		loading = true;
		loginError = '';
		try {
			const res = await auth.login(tokenInput.trim());
			if (res.success) {
				showLoginModal = false;
				tokenInput = '';
			} else {
				loginError = res.message;
			}
		} catch {
			loginError = 'Gagal terhubung ke server';
		} finally {
			loading = false;
		}
	}
</script>

<nav class="navbar">
	<div class="container navbar-inner">
		<a href="/" class="navbar-brand">Elemes LMS</a>

		<div class="navbar-actions">
			<button class="btn-icon" onclick={() => theme.toggle()} title="Toggle tema">
				{$themeDark ? '\u2600\uFE0F' : '\uD83C\uDF19'}
			</button>

			{#if $authLoggedIn}
				<span class="user-label">{$authStudentName}</span>
				<button class="btn btn-danger btn-sm" onclick={() => auth.logout()}>Keluar</button>
			{:else}
				<button class="btn btn-primary btn-sm" onclick={() => (showLoginModal = true)}>
					Masuk
				</button>
			{/if}
		</div>
	</div>
</nav>

<!-- Login modal -->
{#if showLoginModal}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="modal-overlay" onclick={() => (showLoginModal = false)}>
		<div class="modal-card" onclick={(e) => e.stopPropagation()}>
			<h2>Masuk dengan Token</h2>
			<form onsubmit={(e) => { e.preventDefault(); handleLogin(); }}>
				<input
					type="text"
					bind:value={tokenInput}
					placeholder="Masukkan token..."
					disabled={loading}
				/>
				{#if loginError}
					<p class="error">{loginError}</p>
				{/if}
				<button class="btn btn-primary" type="submit" disabled={loading}>
					{loading ? 'Memproses...' : 'Masuk'}
				</button>
			</form>
		</div>
	</div>
{/if}

<style>
	.navbar {
		background: var(--color-primary);
		color: #fff;
		padding: 0.75rem 0;
		position: sticky;
		top: 0;
		z-index: 100;
	}
	.navbar-inner {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.navbar-brand {
		color: #fff;
		font-weight: 700;
		font-size: 1.25rem;
		text-decoration: none;
	}
	.navbar-brand:hover {
		color: #fff;
		text-decoration: none;
	}
	.navbar-actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}
	.user-label {
		font-size: 0.875rem;
		opacity: 0.9;
	}
	.btn-icon {
		background: none;
		border: none;
		cursor: pointer;
		font-size: 1.25rem;
		line-height: 1;
	}
	.btn-sm {
		padding: 0.35rem 0.75rem;
		font-size: 0.8rem;
	}

	/* Modal */
	.modal-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 200;
	}
	.modal-card {
		background: var(--color-bg);
		color: var(--color-text);
		border-radius: var(--radius);
		padding: 2rem;
		width: min(400px, 90vw);
		box-shadow: var(--shadow);
	}
	.modal-card h2 {
		margin-bottom: 1rem;
		font-size: 1.25rem;
	}
	.modal-card input {
		width: 100%;
		padding: 0.6rem 0.75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		font-size: 1rem;
		margin-bottom: 0.75rem;
		background: var(--color-bg-secondary);
		color: var(--color-text);
	}
	.modal-card .btn {
		width: 100%;
		justify-content: center;
	}
	.error {
		color: var(--color-danger);
		font-size: 0.85rem;
		margin-bottom: 0.5rem;
	}
</style>
