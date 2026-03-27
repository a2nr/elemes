<script lang="ts">
	import { authIsTeacher } from '$stores/auth';
	import { env } from '$env/dynamic/public';
</script>

<footer class="footer">
	<div class="container">
		<p>&copy; {env.PUBLIC_COPYRIGHT_TEXT || `${new Date().getFullYear()} Elemes LMS`}</p>
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
</style>
