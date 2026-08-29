<script lang="ts">
	import {
		importPreview,
		importStudents,
		type ImportPreviewResponse
	} from '$services/studentManagement';

	interface Props {
		open: boolean;
		onClose: () => void;
		onImported: () => void;
	}

	let { open, onClose, onImported }: Props = $props();

	let file = $state<File | null>(null);
	let preview = $state<ImportPreviewResponse | null>(null);
	let busy = $state(false);
	let applyBusy = $state(false);
	let error = $state('');
	let imported = $state(false);

	function formatSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	const canApply = $derived(
		!!file &&
			!!preview?.success &&
			preview.summary.rows > 0 &&
			(preview.summary.conflicts?.length ?? 0) === 0 &&
			!applyBusy &&
			!imported
	);
	const conflictCount = $derived(preview?.success ? preview.summary.conflicts?.length ?? 0 : 0);

	async function handleFileChange(event: Event) {
		const input = event.target as HTMLInputElement;
		const selected = input.files?.[0];
		if (!selected) return;
		file = selected;
		preview = null;
		imported = false;
		error = '';
		await runPreview(selected);
	}

	async function runPreview(f: File) {
		busy = true;
		error = '';
		try {
			const res = await importPreview(f);
			preview = res;
			if (!res.success) {
				error = res.message ?? 'Preview gagal — periksa file CSV Anda.';
				if (res.errors?.length) {
					error += '\n' + res.errors.slice(0, 5).join('\n');
				}
			}
		} catch (e) {
			error =
				e instanceof Error && e.message
					? e.message
					: 'Terjadi kesalahan saat membaca file.';
		} finally {
			busy = false;
		}
	}

	async function handleApply() {
		if (!file || applyBusy) return;
		applyBusy = true;
		error = '';
		try {
			const res = await importStudents(file);
			if (res.success) {
				imported = true;
				preview = null;
				file = null;
				onImported();
			} else {
				// file tetap tersedia untuk dikoreksi/retry; token tidak disalin ke state terpisah
				error = res.message ?? 'Import gagal — periksa pesan server.';
				if (res.errors?.length) {
					error += '\n' + res.errors.slice(0, 5).join('\n');
				}
			}
		} catch (e) {
			error =
				e instanceof Error && e.message
					? e.message
					: 'Terjadi kesalahan saat mengimpor.';
		} finally {
			applyBusy = false;
		}
	}

	function close() {
		if (applyBusy) return;
		onClose();
	}
</script>

{#if open}
	<div class="overlay" role="dialog" aria-modal="true" aria-label="Import Siswa" onclick={close}>
		<div class="dialog" onclick={(e) => e.stopPropagation()}>
			<header class="dialog-header">
				<h2>Import Siswa (CSV)</h2>
				<button class="btn-icon" onclick={close} title="Tutup" aria-label="Tutup">&times;</button>
			</header>

			<div class="dialog-body">
				<p class="hint">
					Pilih file CSV hasil <strong>Export CSV</strong> atau file baru.
					Baris dengan <code>student_id</code> kosong (siswa baru) <strong>wajib
					mengisi <code>token</code></strong>; baris dengan <code>student_id</code>
					terisi (hasil export) <strong>boleh dibiarkan token kosong</strong> karena
					token lama dipertahankan. Jangan mengisi token baru untuk
					<code>student_id</code> yang sudah ada — import akan ditolak.
				</p>
				<p class="hint">
					File CSV boleh memakai delimiter <strong>titik koma (<code>;</code>)</strong>
					atau <strong>koma (<code>,</code>)</strong>. Hasil <strong>Export CSV</strong>
					dari aplikasi selalu memakai titik koma (<code>;</code>).
				</p>

				<label class="file-drop">
					<input
						type="file"
						accept=".csv,text/csv"
						onchange={handleFileChange}
						disabled={busy || applyBusy}
					/>
					<span>{file ? file.name : 'Pilih file CSV…'}</span>
					{#if file}
						<small>{formatSize(file.size)}</small>
					{/if}
				</label>

				{#if busy}
					<p class="status">Memvalidasi file…</p>
				{:else if imported}
					<p class="status success">Import berhasil! Siswa baru dibuat, siswa existing dipulihkan, dan progress diterapkan.</p>
				{:else if preview?.success}
					<div class="summary">
						<span><strong>{preview.summary.students_to_create}</strong> siswa baru</span>
						<span><strong>{preview.summary.students_to_update}</strong> dipulihkan/di-update</span>
						<span><strong>{preview.summary.progress_to_create}</strong> progress baru</span>
						<span><strong>{preview.summary.progress_to_restore}</strong> progress dipulihkan</span>
						{#if (preview.summary.progress_to_reset ?? 0) > 0}
							<span><strong>{preview.summary.progress_to_reset}</strong> progress di-reset</span>
						{/if}
						<span class={conflictCount > 0 ? 'bad' : ''}>
							<strong>{conflictCount}</strong> conflict
						</span>
					</div>

					{#if conflictCount > 0}
						<div class="conflict-box">
							<p class="conflict-title">Import ditolak — beberapa siswa sudah ada:</p>
							<ul>
								{#each preview.summary.conflicts.slice(0, 8) as conflict}
									<li>{conflict}</li>
								{/each}
								{#if preview.summary.conflicts.length > 8}
									<li>…dan {preview.summary.conflicts.length - 8} lainnya</li>
								{/if}
							</ul>
							<p class="conflict-hint">
								Perbaiki baris yang bertentangan (mis. hapus token baru dari siswa
								existing, atau kosongkan <code>student_id</code> untuk siswa baru),
								lalu coba import lagi. Token siswa existing tidak pernah diganti lewat import.
							</p>
						</div>
					{:else if preview.summary.rows === 0}
						<p class="status">File tidak berisi data siswa (hanya header).</p>
					{:else}
						<div class="preview-rows">
							{#each (preview.rows ?? []).slice(0, 5) as row}
								<div class="preview-row">
									<span class="line">#{row.line}</span>
									<span class="name">{row.nama_siswa}</span>
									<span class="meta">{row.student_id || 'UUID baru'} · {row.progress_lessons} progress</span>
								</div>
							{/each}
							{#if (preview.rows?.length ?? 0) > 5}
								<p class="more">…dan {(preview.rows?.length ?? 0) - 5} siswa lainnya</p>
							{/if}
						</div>
					{/if}
				{/if}

				{#if error}
					<p class="error">{error}</p>
				{/if}
			</div>

			<footer class="dialog-footer">
				<button class="btn" onclick={close} disabled={applyBusy}>Batal</button>
				<button class="btn btn-primary" onclick={handleApply} disabled={!canApply}>
					{applyBusy ? 'Mengimpor…' : 'Import Siswa'}
				</button>
			</footer>
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}
	.dialog {
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		width: min(560px, 100%);
		max-height: 85vh;
		display: flex;
		flex-direction: column;
		box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
	}
	.dialog-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.9rem 1.1rem;
		border-bottom: 1px solid var(--color-border);
	}
	.dialog-header h2 {
		font-size: 1.05rem;
		margin: 0;
	}
	.btn-icon {
		background: none;
		border: none;
		color: var(--color-text-muted);
		font-size: 1.4rem;
		line-height: 1;
		cursor: pointer;
	}
	.btn-icon:hover {
		color: var(--color-text);
	}
	.dialog-body {
		padding: 1.1rem;
		overflow-y: auto;
	}
	.hint {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin: 0 0 1rem;
	}
	.hint code {
		background: var(--color-bg-secondary);
		padding: 0.1rem 0.3rem;
		border-radius: 4px;
	}
	.file-drop {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		align-items: center;
		justify-content: center;
		padding: 1.25rem;
		border: 1.5px dashed var(--color-border);
		border-radius: var(--radius);
		cursor: pointer;
		font-size: 0.9rem;
	}
	.file-drop:hover {
		border-color: var(--color-primary);
	}
	.file-drop input {
		display: none;
	}
	.file-drop small {
		color: var(--color-text-muted);
	}
	.status {
		margin-top: 0.9rem;
		font-size: 0.9rem;
	}
	.status.success {
		color: var(--color-success);
	}
	.summary {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.2rem;
		margin-top: 1rem;
		padding: 0.7rem 0.9rem;
		background: var(--color-bg-secondary);
		border-radius: var(--radius);
		font-size: 0.9rem;
	}
	.summary .bad strong {
		color: var(--color-danger);
	}
	.conflict-box {
		margin-top: 1rem;
		padding: 0.8rem 0.9rem;
		border: 1px solid var(--color-danger);
		border-radius: var(--radius);
		background: color-mix(in srgb, var(--color-danger) 8%, var(--color-bg));
		font-size: 0.85rem;
	}
	.conflict-title {
		font-weight: 600;
		color: var(--color-danger);
		margin: 0 0 0.4rem;
	}
	.conflict-box ul {
		margin: 0;
		padding-left: 1.1rem;
		color: var(--color-text);
	}
	.conflict-hint {
		margin: 0.5rem 0 0;
		color: var(--color-text-muted);
	}
	.preview-rows {
		margin-top: 0.9rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.preview-row {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		font-size: 0.85rem;
		padding: 0.4rem 0.6rem;
		background: var(--color-bg-secondary);
		border-radius: 6px;
	}
	.preview-row .line {
		color: var(--color-text-muted);
		font-size: 0.75rem;
	}
	.preview-row .name {
		font-weight: 600;
	}
	.preview-row .meta {
		margin-left: auto;
		color: var(--color-text-muted);
	}
	.more {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		margin: 0.2rem 0 0;
	}
	.error {
		margin-top: 0.9rem;
		color: var(--color-danger);
		font-size: 0.85rem;
		white-space: pre-line;
		background: color-mix(in srgb, var(--color-danger) 8%, var(--color-bg));
		padding: 0.6rem 0.8rem;
		border-radius: var(--radius);
		border: 1px solid var(--color-danger);
	}
	.dialog-footer {
		display: flex;
		justify-content: flex-end;
		gap: 0.6rem;
		padding: 0.9rem 1.1rem;
		border-top: 1px solid var(--color-border);
	}
</style>
