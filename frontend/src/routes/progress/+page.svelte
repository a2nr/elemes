<script lang="ts">
	import { get } from 'svelte/store';
	import { authIsTeacher, authToken } from '$stores/auth';
	import { studentSelection } from '$stores/studentSelection';
	import { exportStudentsCsv, triggerBlobDownload } from '$services/studentManagement';
	import StudentImportDialog from '$lib/components/StudentImportDialog.svelte';
	import BulkDeleteStudentsDialog from '$lib/components/BulkDeleteStudentsDialog.svelte';
	import AddStudentDialog from '$lib/components/AddStudentDialog.svelte';

	interface LessonHeader {
		filename: string;
		title: string;
	}

	interface StudentProgress {
		id: string;
		nama_siswa: string;
		role: 'teacher' | 'student';
		completed_count: number;
		[key: string]: string | number | boolean;
	}

	// `_diag_unmastered` dikirim backend sebagai JSON string array of question_id.
	function parseUnmastered(raw: string | number | boolean | undefined): string[] {
		if (typeof raw !== 'string') return [];
		try {
			const parsed = JSON.parse(raw);
			return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : [];
		} catch {
			return [];
		}
	}

	let students = $state<StudentProgress[]>([]);
	let lessons = $state<LessonHeader[]>([]);
	let loading = $state(true);
	let exportBusy = $state(false);
	let exportError = $state('');
	let importOpen = $state(false);
	let deleteOpen = $state(false);
	let addOpen = $state(false);
	let headerCheckbox = $state<HTMLInputElement | undefined>();

	// Reactively load data when auth is ready
	$effect(() => {
		if ($authIsTeacher && $authToken) {
			loadData();
		} else if (!$authIsTeacher) {
			// If not a teacher, we can stop loading (will show "no access" message)
			loading = false;
		}
	});

	async function loadData() {
		if (!$authIsTeacher || !$authToken) return;

		loading = true;
		try {
			const res = await fetch(`/api/progress-report.json?token=${encodeURIComponent($authToken)}`);
			const data = await res.json();
			students = data.students ?? [];
			lessons = data.lessons ?? [];
			// Hanya siswa yang bisa di-select untuk bulk export/delete (guru hanya ditampilkan)
			studentSelection.setAvailable(
				students.filter((s) => s.role === 'student').map((s) => s.id)
			);
		} catch {
			// API not available
		} finally {
			loading = false;
		}
	}

	async function handleReset(studentId: string, lessonName: string, studentName: string) {
		if (!window.confirm(`Apakah Anda yakin ingin me-reset progres kuis "${lessonName}" untuk siswa "${studentName}"?`)) {
			return;
		}

		try {
			const res = await fetch('/api/reset-progress', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					teacher_token: $authToken,
					student_id: studentId,
					lesson_name: lessonName
				})
			});
			const data = await res.json();
			if (data.success) {
				await loadData();
			} else {
				alert('Gagal me-reset: ' + data.message);
			}
		} catch (err) {
			alert('Terjadi kesalahan saat menghubungi server.');
		}
	}

	async function handleExport() {
		if (exportBusy) return;
		exportBusy = true;
		exportError = '';
		try {
			const { blob, filename } = await exportStudentsCsv(get(studentSelection.selected), fetch);
			triggerBlobDownload(blob, filename);
		} catch (err) {
			exportError = err instanceof Error ? err.message : 'Gagal mengekspor CSV.';
		} finally {
			exportBusy = false;
		}
	}

	function handleImported() {
		importOpen = false;
		studentSelection.clear();
		loadData();
	}

	function handleDeleted() {
		deleteOpen = false;
		studentSelection.clear();
		loadData();
	}

	function handleAdded() {
		addOpen = false;
		studentSelection.clear();
		loadData();
	}

	function handleHeaderCheckbox() {
		if (get(studentSelection.allSelected)) {
			studentSelection.clear();
		} else {
			studentSelection.selectAll();
		}
	}

	// Reaktif: baca store via prefix $ (Svelte 5 runes).
	// CATATAN: get() dari svelte/store TIDAK ter-track oleh $derived (hanya snapshot
	// sekali) sehingga tombol delete/counter tidak pernah ter-update. Prefix $ membungkus
	// store ke $.store_get yang terdaftar ke sistem reaktivitas runes.
	const {
		selected: selectedStore,
		count: countStore,
		allSelected: allSelectedStore,
		someSelected: someSelectedStore
	} = studentSelection;
	const selectedIds = $derived($selectedStore);
	const selectionCount = $derived($countStore);
	const allSelected = $derived($allSelectedStore);
	const someSelected = $derived($someSelectedStore);

	// Indeterminate state untuk checkbox header
	$effect(() => {
		if (headerCheckbox) {
			headerCheckbox.indeterminate = someSelected && !allSelected;
		}
	});

	const selectedStudents = $derived(students.filter((s) => selectedIds.includes(s.id)));

	const totalLessons = $derived(lessons.length);
	// Hanya siswa yang dihitung untuk ringkasan & empty-state (guru hanya ditampilkan)
	const studentRows = $derived(students.filter((s) => s.role === 'student'));
</script>

<svelte:head>
	<title>Laporan Progress - Elemes LMS</title>
</svelte:head>

<h1>Laporan Progress Siswa</h1>

{#if loading}
	<p class="loading">Memuat data...</p>
{:else if !$authIsTeacher}
	<p class="empty">Anda tidak memiliki akses ke halaman ini.</p>
{:else}
	<div class="summary-bar">
		<span><strong>{studentRows.length}</strong> siswa</span>
		<span><strong>{totalLessons}</strong> pelajaran</span>

		{#if selectionCount > 0}
			<span class="selection-count">
				<strong>{selectionCount}</strong> siswa dipilih
			</span>
		{/if}

		<div class="actions">
			{#if exportError}
				<span class="error-inline">{exportError}</span>
			{/if}

			<button
				class="btn btn-sm btn-secondary"
				onclick={handleExport}
				disabled={exportBusy}
				title="Unduh CSV siswa (token kosong) untuk diedit dan diimpor ulang — tetap tersedia saat belum ada siswa (header-only)"
			>
				{#if exportBusy}
					Mengekspor…
				{:else if selectionCount > 0}
					&#8595; Export {selectionCount} Siswa
				{:else}
					&#8595; Export CSV
				{/if}
			</button>

			<button
				class="btn btn-sm btn-secondary"
				onclick={() => (addOpen = true)}
				title="Tambah satu siswa dengan nama & token"
			>
				+ Tambah Siswa
			</button>

			<button
				class="btn btn-sm btn-secondary"
				onclick={() => (importOpen = true)}
				title="Import CSV — siswa baru dibuat, siswa existing dipulihkan/di-update"
			>
				&#8593; Import CSV
			</button>

			<button
				class="btn btn-sm btn-danger"
				onclick={() => (deleteOpen = true)}
				disabled={selectionCount === 0}
				title="Hapus siswa terpilih beserta token dan progress"
			>
				&#128465; Hapus {selectionCount} Siswa
			</button>

			<a href="/api/progress-report/export-csv?token={encodeURIComponent($authToken)}" class="btn btn-sm btn-secondary">
				Export Laporan
			</a>
		</div>
	</div>

	{#if studentRows.length === 0}
		<p class="empty">Belum ada data siswa. Gunakan <strong>Import CSV</strong> untuk menambah siswa pertama.</p>
	{:else}
		<div class="table-wrapper">
			<table>
				<thead>
					<tr>
						<th class="checkbox-col">
							<input
								type="checkbox"
								bind:this={headerCheckbox}
								checked={allSelected}
								onchange={handleHeaderCheckbox}
								aria-label="Pilih semua siswa"
							/>
						</th>
						<th class="sticky-col">Nama Siswa</th>
						{#each lessons as lesson}
							<th title={lesson.filename}>{lesson.title}</th>
						{/each}
						<th>Selesai</th>
					</tr>
				</thead>
				<tbody>
					{#each students as student}
						{@const isChecked = selectedIds.includes(student.id as string)}
						{@const isTeacher = student.role === 'teacher'}
						<tr class:selected={isChecked}>
							<td class="checkbox-col">
								{#if isTeacher}
									<span class="teacher-no-select" aria-label="Guru tidak dapat dipilih" title="Guru tidak dapat dipilih untuk aksi bulk">—</span>
								{:else}
									<input
										type="checkbox"
										checked={isChecked}
										onchange={() => studentSelection.toggle(student.id as string)}
										aria-label={`Pilih ${student.nama_siswa}`}
									/>
								{/if}
							</td>
							<td class="sticky-col student-name">
								{student.nama_siswa}
								{#if isTeacher}
									<span class="badge teacher-badge">Guru</span>
								{/if}
							</td>
							{#each lessons as lesson}
								{@const key = lesson.filename.replace('.md', '')}
								{@const status = student[key]}
								{@const violation = student[key + '_has_violation']}
								{@const violationReason = student[key + '_termination_reason']}
								{@const violationTime = student[key + '_attempt_finished_at']}
								{@const evalScore = student[key + '_eval']}
								{@const diagScore = student[key + '_diag']}
								{@const diagUnmastered = parseUnmastered(student[key + '_diag_unmastered'])}
								<td class="status-cell">
									<div class="cell-content">
										{#if status === 'completed'}
											<span class="badge done">&#10003;</span>
										{:else if status && status !== 'not_started'}
											<span class="badge score">{status}</span>
										{:else}
											<span class="badge empty">&mdash;</span>
										{/if}

										{#if violation}
											<span
												class="badge violation"
												title="Pelanggaran anti-cheat — {violationReason}{violationTime ? ' pada ' + violationTime : ''}"
											>
												&#9888; Pelanggaran
											</span>
										{/if}

										{#if evalScore}
											<span class="badge eval" title="Skor evaluasi (skor resmi)">Eval: {evalScore}</span>
										{/if}
										{#if diagScore}
											<span class="badge diag" title="Skor soal diagnostik">Diag: {diagScore}</span>
											{#if diagUnmastered.length > 0}
												<span
													class="badge unmastered"
													title="Belum dikuasai: {diagUnmastered.join(', ')}"
												>
													{diagUnmastered.length} belum dikuasai
												</span>
											{/if}
										{/if}

										{#if status && status !== 'not_started'}
											<button
												class="btn-reset-mini"
												onclick={() => handleReset(student.id as string, key, student.nama_siswa)}
												title="Reset Progres"
											>
												↻
											</button>
										{/if}
									</div>
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

	<StudentImportDialog
		open={importOpen}
		onClose={() => (importOpen = false)}
		onImported={handleImported}
	/>
	<AddStudentDialog
		open={addOpen}
		onClose={() => (addOpen = false)}
		onAdded={handleAdded}
	/>
	<BulkDeleteStudentsDialog
		open={deleteOpen}
		studentNames={selectedStudents.map((s) => ({ id: s.id as string, nama_siswa: s.nama_siswa }))}
		onClose={() => (deleteOpen = false)}
		onDeleted={handleDeleted}
	/>
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
		flex-wrap: wrap;
		gap: 1.5rem;
		margin-bottom: 1rem;
		padding: 0.75rem 1rem;
		background: var(--color-bg-secondary);
		border-radius: var(--radius);
		font-size: 0.9rem;
	}
	.selection-count {
		color: var(--color-primary);
	}
	.actions {
		margin-left: auto;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.error-inline {
		color: var(--color-danger);
		font-size: 0.8rem;
	}

	.btn-sm {
		padding: 0.3rem 0.75rem;
		font-size: 0.8rem;
		border-radius: var(--radius);
		cursor: pointer;
		text-decoration: none;
		transition: all 0.15s;
	}
	.btn-secondary {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		color: var(--color-text);
	}
	.btn-secondary:hover:not(:disabled) {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}
	.btn-danger {
		background: var(--color-bg);
		border: 1px solid var(--color-danger);
		color: var(--color-danger);
	}
	.btn-danger:hover:not(:disabled) {
		background: var(--color-danger);
		color: #fff;
	}
	.btn-sm:disabled {
		opacity: 0.45;
		cursor: not-allowed;
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
	.checkbox-col {
		width: 2.2rem;
		padding: 0.5rem 0.25rem;
	}
	.checkbox-col input {
		cursor: pointer;
		accent-color: var(--color-primary);
	}
	tr.selected td {
		background: color-mix(in srgb, var(--color-primary) 6%, var(--color-bg));
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
	.badge.teacher-badge {
		margin-left: 0.4rem;
		color: var(--color-primary);
		background: color-mix(in srgb, var(--color-primary) 10%, var(--color-bg));
		border: 1px solid color-mix(in srgb, var(--color-primary) 40%, var(--color-bg));
		border-radius: 999px;
		padding: 0.1rem 0.45rem;
		font-size: 0.65rem;
		font-weight: 700;
		white-space: nowrap;
	}
	.teacher-no-select {
		color: var(--color-text-muted);
		font-size: 0.9rem;
	}
	.status-cell {
		min-width: 40px;
	}
	.badge.done {
		color: var(--color-success);
		font-weight: bold;
	}
	.badge.score {
		color: var(--color-primary);
		font-weight: 600;
		font-size: 0.75rem;
	}
	.badge.empty {
		color: var(--color-text-muted);
	}
	.badge.violation {
		color: var(--color-danger, #e8590c);
		background: color-mix(in srgb, var(--color-danger, #e8590c) 10%, var(--color-bg));
		border: 1px solid color-mix(in srgb, var(--color-danger, #e8590c) 40%, var(--color-bg));
		border-radius: 999px;
		padding: 0.1rem 0.45rem;
		font-size: 0.65rem;
		font-weight: 700;
		white-space: nowrap;
	}
	.badge.eval, .badge.diag, .badge.unmastered {
		border-radius: 999px;
		padding: 0.1rem 0.45rem;
		font-size: 0.65rem;
		font-weight: 700;
		white-space: nowrap;
	}
	.badge.eval {
		color: var(--color-primary);
		background: color-mix(in srgb, var(--color-primary) 10%, var(--color-bg));
		border: 1px solid color-mix(in srgb, var(--color-primary) 40%, var(--color-bg));
	}
	.badge.diag {
		color: var(--color-text-muted);
		background: var(--color-bg-secondary);
		border: 1px solid var(--color-border);
	}
	.badge.unmastered {
		color: var(--color-danger, #e8590c);
		background: color-mix(in srgb, var(--color-danger, #e8590c) 10%, var(--color-bg));
		border: 1px solid color-mix(in srgb, var(--color-danger, #e8590c) 40%, var(--color-bg));
	}
	.cell-content {
		display: flex;
		align-items: center;
		justify-content: center;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.btn-reset-mini {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 4px;
		color: var(--color-text-muted);
		cursor: pointer;
		font-size: 0.7rem;
		padding: 0 0.15rem;
		line-height: 1.1;
		transition: all 0.2s;
	}
	.btn-reset-mini:hover {
		border-color: #fa5252;
		color: #fa5252;
		background: #fff5f5;
	}
	.completion-count {
		font-weight: 600;
		min-width: 60px;
	}
</style>
