<script lang="ts">
	import { onMount } from 'svelte';
	import { auth, authIsTeacher } from '$stores/auth';

	interface LessonHeader {
		filename: string;
		title: string;
	}

	interface StudentProgress {
		nama_siswa: string;
		completed_count: number;
		[key: string]: string | number;
	}

	let students = $state<StudentProgress[]>([]);
	let lessons = $state<LessonHeader[]>([]);
	let loading = $state(true);

	onMount(async () => {
		if (!$authIsTeacher) {
			loading = false;
			return;
		}

		try {
			const res = await fetch(`/api/progress-report.json?token=${encodeURIComponent(auth.token)}`);
			const data = await res.json();
			students = data.students ?? [];
			lessons = data.lessons ?? [];
		} catch {
			// API not available
		} finally {
			loading = false;
		}
	});

	const totalLessons = $derived(lessons.length);
</script>

<svelte:head>
	<title>Laporan Progress - Elemes LMS</title>
</svelte:head>

<h1>Laporan Progress Siswa</h1>

{#if !$authIsTeacher}
	<p class="empty">Anda tidak memiliki akses ke halaman ini.</p>
{:else if loading}
	<p class="loading">Memuat data...</p>
{:else if students.length === 0}
	<p class="empty">Belum ada data siswa.</p>
{:else}
	<div class="summary-bar">
		<span><strong>{students.length}</strong> siswa</span>
		<span><strong>{totalLessons}</strong> pelajaran</span>
		<a href="/api/progress-report/export-csv?token={encodeURIComponent(auth.token)}" class="btn btn-secondary btn-sm">
			Export CSV
		</a>
	</div>

	<div class="table-wrapper">
		<table>
			<thead>
				<tr>
					<th class="sticky-col">Nama Siswa</th>
					{#each lessons as lesson}
						<th title={lesson.filename}>{lesson.title}</th>
					{/each}
					<th>Selesai</th>
				</tr>
			</thead>
			<tbody>
				{#each students as student}
					<tr>
						<td class="sticky-col student-name">{student.nama_siswa}</td>
						{#each lessons as lesson}
							{@const key = lesson.filename.replace('.md', '')}
							{@const status = student[key]}
							<td class="status-cell">
								{#if status === 'completed'}
									<span class="badge done">&#10003;</span>
								{:else}
									<span class="badge empty">&mdash;</span>
								{/if}
							</td>
						{/each}
						<td class="completion-count">
							{student.completed_count}/{totalLessons}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

<style>
	h1 {
		font-size: 1.5rem;
		margin-bottom: 1rem;
	}
	.loading, .empty {
		text-align: center;
		padding: 3rem;
		color: var(--color-text-muted);
	}

	.summary-bar {
		display: flex;
		align-items: center;
		gap: 1.5rem;
		margin-bottom: 1rem;
		padding: 0.75rem 1rem;
		background: var(--color-bg-secondary);
		border-radius: var(--radius);
		font-size: 0.9rem;
	}
	.summary-bar .btn-sm {
		margin-left: auto;
		padding: 0.3rem 0.75rem;
		font-size: 0.8rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		color: var(--color-text);
		border-radius: var(--radius);
		text-decoration: none;
	}

	.table-wrapper {
		overflow-x: auto;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}
	th, td {
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--color-border);
		text-align: center;
		white-space: nowrap;
	}
	th {
		background: var(--color-bg-secondary);
		font-weight: 600;
		font-size: 0.8rem;
		position: sticky;
		top: 0;
	}
	.sticky-col {
		position: sticky;
		left: 0;
		background: var(--color-bg);
		z-index: 1;
		text-align: left;
	}
	th.sticky-col {
		background: var(--color-bg-secondary);
		z-index: 2;
	}
	.student-name {
		font-weight: 500;
		min-width: 150px;
	}
	.status-cell {
		min-width: 40px;
	}
	.badge.done {
		color: var(--color-success);
		font-weight: bold;
	}
	.badge.empty {
		color: var(--color-text-muted);
	}
	.completion-count {
		font-weight: 600;
		min-width: 60px;
	}
</style>
