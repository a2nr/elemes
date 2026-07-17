<script lang="ts">
	import { authIsTeacher } from '$stores/auth';
	import { env } from '$env/dynamic/public';
</script>

<footer class="footer">
	<div class="container">
		<p>&copy; {env.PUBLIC_COPYRIGHT_TEXT || `${new Date().getFullYear()} Elemes LMS`} <span class="version-badge">v16</span></p>
		{#if $authIsTeacher}
			<p><a href="/progress" class="teacher-link">Laporan Progress Siswa</a></p>
		{/if}
	</div>
</footer>

<style>
	.footer {
		background: var(--color-bg-secondary);
		border-top: 1px solid var(--color-border);
		padding: 1rem 0;
		text-align: center;
		font-size: 0.8rem;
		color: var(--color-text-muted);
		margin-top: auto;
	}
	.teacher-link {
		color: var(--color-primary);
		text-decoration: none;
		font-weight: 500;
	}
	.teacher-link:hover {
		text-decoration: underline;
	}
	.version-badge {
		display: inline-block;
		font-size: 0.65rem;
		background: var(--color-primary, #3b82f6);
		color: white;
		padding: 1px 5px;
		border-radius: 3px;
		margin-left: 6px;
		vertical-align: middle;
		opacity: 0.7;
	}
</style>
