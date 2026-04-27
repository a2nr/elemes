<script lang="ts">
	import { auth, authLoggedIn, authStudentName } from '$stores/auth';
	import { theme, themeDark } from '$stores/theme';
	import { lessonContext } from '$stores/lessonContext';
	import ProgressBadge from '$components/ProgressBadge.svelte';
	import { env } from '$env/dynamic/public';

	let showDropdown = $state(false);
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

<svelte:window onclick={() => (showDropdown = false)} />

<nav class="navbar" onclickcapture={() => auth.recordActivity()}>
	<div class="container navbar-inner">
		<div class="navbar-left">
			<div class="nav-dropdown">
				<button type="button" class="btn-icon-sm dropdown-toggle" onclick={(e) => { e.stopPropagation(); showDropdown = !showDropdown; }} title="Menu">
					<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="12" x2="20" y2="12"></line><line x1="4" y1="6" x2="20" y2="6"></line><line x1="4" y1="18" x2="20" y2="18"></line></svg>
				</button>
				{#if showDropdown}
					<!-- svelte-ignore a11y_click_events_have_key_events -->
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<div class="dropdown-menu" onclick={(e) => e.stopPropagation()}>
						<button type="button" class="dropdown-item" onclick={() => { theme.toggle(); showDropdown = false; }}>
							{#if $themeDark}
								<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
								Tema Terang
							{:else}
								<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
								Tema Gelap
							{/if}
						</button>
						<a href="/help" target="_blank" class="dropdown-item" onclick={() => (showDropdown = false)}>
							<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
							Bantuan
						</a>
						<div class="dropdown-divider"></div>
						{#if $authLoggedIn}
							<button type="button" class="dropdown-item" onclick={() => { auth.logout(); showDropdown = false; }}>
								<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
								Keluar
							</button>
						{:else}
							<button type="button" class="dropdown-item" onclick={() => { (showLoginModal = true); (showDropdown = false); }}>
								<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h4"></path><polyline points="10 17 15 12 10 7"></polyline><line x1="15" y1="12" x2="3" y2="12"></line></svg>
								Masuk
							</button>
						{/if}
					</div>
				{/if}
			</div>

			{#if $lessonContext}
				<a href="/" class="nav-home-btn" title="Semua Pelajaran">
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
				</a>
			{:else}
				<a href="/" class="navbar-brand">{env.PUBLIC_APP_BAR_TITLE || 'Elemes LMS'}</a>
			{/if}

			{#if $lessonContext}
				<h1 class="navbar-lesson-title">{$lessonContext.title}</h1>
				{#if $lessonContext.completed && $authLoggedIn}
					<ProgressBadge completed={true} />
				{/if}
			{/if}
		</div>

		<div class="navbar-actions">
			{#if $authLoggedIn}
				<span class="user-label">{$authStudentName}</span>
			{/if}

			{#if $lessonContext?.nextLesson}
				<a href="/lesson/{$lessonContext.nextLesson.filename}" class="btn btn-nav-next" title="{$lessonContext.nextLesson.title}">
					{$lessonContext.nextLesson.title} &rsaquo;
				</a>
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

	/* ── Dropdown ──────────────────────────────────── */
	.nav-dropdown {
		position: relative;
		display: flex;
		align-items: center;
		margin-right: 0.25rem;
	}
	.dropdown-toggle {
		color: rgba(255, 255, 255, 0.85);
		transition: color 0.15s;
		display: flex;
		align-items: center;
	}
	.dropdown-toggle:hover {
		color: #fff;
	}
	.dropdown-menu {
		position: absolute;
		top: 100%;
		left: 0;
		margin-top: 0.5rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
		min-width: 160px;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		z-index: 200;
	}
	.dropdown-item {
		padding: 0.6rem 1rem;
		background: none;
		border: none;
		color: var(--color-text);
		text-align: left;
		font-size: 0.85rem;
		font-weight: 500;
		cursor: pointer;
		text-decoration: none;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		transition: background 0.15s;
	}
	.dropdown-item:hover {
		background: var(--color-bg-secondary);
		color: var(--color-primary);
		text-decoration: none;
	}
	.dropdown-divider {
		height: 1px;
		background: var(--color-border);
		margin: 0.25rem 0;
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
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 120px;
	}
	.btn-icon-sm {
		background: none;
		border: none;
		cursor: pointer;
		font-size: 1rem;
		line-height: 1;
		padding: 0.2rem;
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
		.navbar-inner {
			gap: 0.35rem;
		}
		.navbar-lesson-title {
			font-size: 0.9rem;
		}
		.user-label {
			display: inline-block;
			font-size: 0.65rem;
			max-width: 80px;
		}
		.btn-nav-next {
			font-size: 0.7rem;
			padding: 0.2rem 0.4rem;
			max-width: 90px;
		}
	}
</style>