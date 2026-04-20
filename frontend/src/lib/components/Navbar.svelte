<script lang="ts">
	import { auth, authLoggedIn, authStudentName } from '$stores/auth';
	import { theme, themeDark } from '$stores/theme';
	import { lessonContext } from '$stores/lessonContext';
	import ProgressBadge from '$components/ProgressBadge.svelte';
	import { env } from '$env/dynamic/public';

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
				location.reload();
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

<nav class="navbar" onclick={() => auth.recordActivity()}>
	<div class="container navbar-inner">
		{#if $lessonContext}
			<!-- Lesson mode -->
			<div class="navbar-left">
				<a href="/" class="nav-home-btn" title="Semua Pelajaran">
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
				</a>
				<h1 class="navbar-lesson-title">{$lessonContext.title}</h1>
				{#if $lessonContext.completed && $authLoggedIn}
					<ProgressBadge completed={true} />
				{/if}
			</div>
		{:else}
			<!-- Home mode -->
			<a href="/" class="navbar-brand">{env.PUBLIC_APP_BAR_TITLE || 'Elemes LMS'}</a>
		{/if}

		<div class="navbar-actions">
			{#if $lessonContext?.nextLesson}
				<a href="/lesson/{$lessonContext.nextLesson.filename}" class="btn btn-nav-next" title="{$lessonContext.nextLesson.title}">
					{$lessonContext.nextLesson.title} &rsaquo;
				</a>
			{/if}

			<button class="btn-icon-sm" onclick={() => theme.toggle()} title="Toggle tema">
				{$themeDark ? '\u2600\uFE0F' : '\uD83C\uDF19'}
			</button>

			<a href="/help" target="_blank" class="nav-help-link" title="Panduan Penggunaan">
				Bantuan
			</a>

			{#if $authLoggedIn}
				<span class="user-label">{$authStudentName}</span>
				<button class="btn btn-danger btn-xs" onclick={() => auth.logout()}>Keluar</button>
			{:else}
				<button class="btn btn-primary btn-xs" onclick={() => (showLoginModal = true)}>
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
		padding: 0.5rem 0;
		position: sticky;
		top: 0;
		z-index: 100;
	}
	.navbar-inner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	/* ── Home mode ─────────────────────────────────── */
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

	/* ── Lesson mode (left section) ────────────────── */
	.navbar-left {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
		flex: 1;
	}
	.nav-home-btn {
		color: rgba(255, 255, 255, 0.85);
		text-decoration: none;
		padding: 0.3rem;
		border-radius: 6px;
		transition: background 0.15s, color 0.15s;
		flex-shrink: 0;
		display: flex;
		align-items: center;
	}
	.nav-home-btn:hover {
		background: rgba(255, 255, 255, 0.15);
		color: #fff;
		text-decoration: none;
	}
	.navbar-lesson-title {
		font-size: 1.15rem;
		font-weight: 700;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		min-width: 0;
		margin: 0;
		line-height: 1.3;
	}

	/* ── Right section ─────────────────────────────── */
	.navbar-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-shrink: 0;
	}
	.btn-nav-next {
		background: rgba(255, 255, 255, 0.2);
		color: #fff;
		border: none;
		border-radius: 6px;
		padding: 0.25rem 0.6rem;
		font-size: 0.75rem;
		font-weight: 600;
		text-decoration: none;
		transition: background 0.15s;
		white-space: nowrap;
		max-width: 180px;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.btn-nav-next:hover {
		background: rgba(255, 255, 255, 0.3);
		color: #fff;
		text-decoration: none;
	}
	.user-label {
		font-size: 0.8rem;
		opacity: 0.9;
	}
	.btn-icon-sm {
		background: none;
		border: none;
		cursor: pointer;
		font-size: 1rem;
		line-height: 1;
		padding: 0.2rem;
	}
	.btn-xs {
		padding: 0.25rem 0.6rem;
		font-size: 0.75rem;
	}
	.nav-help-link {
		color: #fff;
		text-decoration: none;
		font-size: 0.75rem;
		font-weight: 600;
		padding: 0.25rem 0.6rem;
		border: 1px solid rgba(255, 255, 255, 0.3);
		border-radius: 6px;
		transition: background 0.15s;
	}
	.nav-help-link:hover {
		background: rgba(255, 255, 255, 0.15);
		color: #fff;
		text-decoration: none;
	}

	/* ── Modal ──────────────────────────────────────── */
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

	/* ── Mobile ─────────────────────────────────────── */
	@media (max-width: 768px) {
		.navbar-lesson-title {
			font-size: 0.9rem;
		}
		.user-label {
			display: none;
		}
		.btn-nav-next {
			font-size: 0.7rem;
			padding: 0.2rem 0.4rem;
			max-width: 100px;
		}
	}
</style>
