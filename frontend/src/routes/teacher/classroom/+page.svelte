<script lang="ts">
	import { get } from 'svelte/store';
	import { authIsTeacher, authToken } from '$stores/auth';
	import { studentSelection } from '$stores/studentSelection';
	import { exportStudentsCsv, triggerBlobDownload } from '$services/studentManagement';
	import StudentImportDialog from '$lib/components/StudentImportDialog.svelte';
	import BulkDeleteStudentsDialog from '$lib/components/BulkDeleteStudentsDialog.svelte';
	import AddStudentDialog from '$lib/components/AddStudentDialog.svelte';

	interface StudentItem {
		id: string;
		nama_siswa: string;
		role: 'teacher' | 'student';
		completed_count: number;
		[key: string]: string | number | boolean;
	}

	let students = $state<StudentItem[]>([]);
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
			loading = false;
		}
	});

	async function loadData() {
		if (!$authIsTeacher || !$authToken) return;

		loading = true;
		try {
			const res = await fetch(`/api/progress-report.json?token=${encodeURIComponent($authToken)}&_t=${Date.now()}`, {
				cache: 'no-store'
			});
			const data = await res.json();
			students = data.students ?? [];
			studentSelection.setAvailable(
				students.filter((s) => s.role === 'student').map((s) => s.id)
			);
		} catch {
			// API not available
		} finally {
			loading = false;
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

	$effect(() => {
		if (headerCheckbox) {
			headerCheckbox.indeterminate = someSelected && !allSelected;
		}
	});

	const selectedStudents = $derived(students.filter((s) => selectedIds.includes(s.id)));
	const studentRows = $derived(students.filter((s) => s.role === 'student'));
</script>

<svelte:head>
	<title>Manajemen Kelas - Elemes LMS</title>
</svelte:head>

<div class="header-section">
	<div>
		<h1>Manajemen Kelas & Siswa</h1>
		<p class="subtitle">Kelola akun siswa, impor/ekspor data kelas, dan pantau ringkasan siswa.</p>
	</div>
	<div class="header-actions">
		<a href="/teacher/progress" class="btn btn-sm btn-outline">
			Lihat Perkembangan Siswa &rarr;
		</a>
	</div>
</div>

{#if loading}
	<p class="loading">Memuat data kelas...</p>
{:else if !$authIsTeacher}
	<p class="empty">Anda tidak memiliki akses ke halaman ini.</p>
{:else}
	<div class="summary-bar">
		<span><strong>{studentRows.length}</strong> siswa terdaftar</span>

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
				title="Unduh CSV siswa (token kosong) untuk diedit dan diimpor ulang"
			>
				{#if exportBusy}
					Mengekspor…
				{:else if selectionCount > 0}
					&#8595; Export {selectionCount} Siswa
				{:else}
					&#8595; Export CSV Siswa
				{/if}
			</button>

			<button
				class="btn btn-sm btn-secondary"
				onclick={() => (addOpen = true)}
				title="Tambah satu siswa baru secara manual"
			>
				+ Tambah Siswa
			</button>

			<button
				class="btn btn-sm btn-secondary"
				onclick={() => (importOpen = true)}
				title="Import data siswa dari berkas CSV"
			>
				&#8593; Import CSV
			</button>

			<button
				class="btn btn-sm btn-danger"
				onclick={() => (deleteOpen = true)}
				disabled={selectionCount === 0}
				title="Hapus siswa terpilih beserta token dan progresnya"
			>
				&#128465; Hapus {selectionCount} Siswa
			</button>
		</div>
	</div>

	{#if studentRows.length === 0}
		<div class="empty-box">
			<p class="empty-title">Belum ada data siswa</p>
			<p class="empty-desc">Gunakan tombol <strong>Import CSV</strong> untuk mengimpor daftar siswa atau <strong>Tambah Siswa</strong> untuk memasukkan siswa satu per satu.</p>
			<div class="empty-actions">
				<button class="btn btn-primary" onclick={() => (importOpen = true)}>&#8593; Import CSV</button>
				<button class="btn btn-secondary" onclick={() => (addOpen = true)}>+ Tambah Siswa</button>
			</div>
		</div>
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
						<th class="text-left">Nama Siswa</th>
						<th class="text-center">Peran</th>
						<th class="text-center">Materi Diselesaikan</th>
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
							<td class="text-left student-name-cell">
								<span class="student-name">{student.nama_siswa}</span>
							</td>
							<td class="text-center">
								{#if isTeacher}
									<span class="badge teacher-badge">Guru</span>
								{:else}
									<span class="badge student-badge">Siswa</span>
								{/if}
							</td>
							<td class="text-center completion-count">
								<strong>{student.completed_count}</strong> materi
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
	.header-section {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		flex-wrap: wrap;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}
	h1 {
		font-size: 1.5rem;
		margin: 0 0 0.25rem 0;
	}
	.subtitle {
		color: var(--color-text-muted);
		font-size: 0.9rem;
		margin: 0;
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

	.btn {
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		font-weight: 500;
		border-radius: var(--radius);
		cursor: pointer;
		text-decoration: none;
		transition: all 0.15s;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.btn-primary {
		background: var(--color-primary);
		border: 1px solid var(--color-primary);
		color: #fff;
	}
	.btn-primary:hover {
		opacity: 0.9;
	}
	.btn-sm {
		padding: 0.35rem 0.75rem;
		font-size: 0.8rem;
	}
	.btn-outline {
		background: transparent;
		border: 1px solid var(--color-primary);
		color: var(--color-primary);
	}
	.btn-outline:hover {
		background: var(--color-primary);
		color: #fff;
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
	.btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.empty-box {
		text-align: center;
		padding: 3rem 1.5rem;
		background: var(--color-bg-secondary);
		border: 1px dashed var(--color-border);
		border-radius: var(--radius);
		margin: 1.5rem 0;
	}
	.empty-title {
		font-size: 1.1rem;
		font-weight: 600;
		margin: 0 0 0.5rem 0;
	}
	.empty-desc {
		color: var(--color-text-muted);
		max-width: 450px;
		margin: 0 auto 1.5rem auto;
		font-size: 0.9rem;
	}
	.empty-actions {
		display: flex;
		gap: 0.75rem;
		justify-content: center;
	}

	.table-wrapper {
		overflow-x: auto;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-bg);
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.875rem;
	}
	th, td {
		padding: 0.75rem 1rem;
		border-bottom: 1px solid var(--color-border);
	}
	th {
		background: var(--color-bg-secondary);
		font-weight: 600;
		font-size: 0.8rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}
	.text-left {
		text-align: left;
	}
	.text-center {
		text-align: center;
	}
	.checkbox-col {
		width: 2.5rem;
		text-align: center;
		padding: 0.75rem 0.5rem;
	}
	.checkbox-col input {
		cursor: pointer;
		accent-color: var(--color-primary);
	}
	tr.selected td {
		background: color-mix(in srgb, var(--color-primary) 6%, var(--color-bg));
	}
	.student-name-cell {
		font-weight: 500;
	}
	.student-name {
		font-size: 0.9rem;
	}
	.badge {
		display: inline-block;
		border-radius: 999px;
		padding: 0.15rem 0.6rem;
		font-size: 0.7rem;
		font-weight: 600;
	}
	.badge.teacher-badge {
		color: var(--color-primary);
		background: color-mix(in srgb, var(--color-primary) 10%, var(--color-bg));
		border: 1px solid color-mix(in srgb, var(--color-primary) 40%, var(--color-bg));
	}
	.badge.student-badge {
		color: var(--color-text-muted);
		background: var(--color-bg-secondary);
		border: 1px solid var(--color-border);
	}
	.teacher-no-select {
		color: var(--color-text-muted);
		font-size: 0.9rem;
	}
	.completion-count {
		color: var(--color-text);
		font-size: 0.85rem;
	}
</style>
