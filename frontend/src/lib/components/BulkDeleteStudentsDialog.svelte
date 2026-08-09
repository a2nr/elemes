<script lang="ts">
	import { bulkDeleteStudents } from '$services/studentManagement';

	interface Props {
		open: boolean;
		studentNames: { id: string; nama_siswa: string }[];
		onClose: () => void;
		onDeleted: (deletedIds: string[]) => void;
	}

	let { open, studentNames, onClose, onDeleted }: Props = $props();

	let busy = $state(false);
	let error = $state('');

	const count = $derived(studentNames.length);
	const previewNames = $derived(studentNames.slice(0, 3).map((s) => s.nama_siswa));
	const extra = $derived(Math.max(0, count - 3));

	async function handleDelete() {
		if (busy || count === 0) return;
		busy = true;
		error = '';
		try {
			const res = await bulkDeleteStudents(studentNames.map((s) => s.id));
			if (res.success) {
				onDeleted(res.deleted_ids ?? studentNames.map((s) => s.id));
			} else {
				error = res.message ?? 'Gagal menghapus siswa.';
			}
		} catch {
			error = 'Terjadi kesalahan saat menghubungi server.';
		} finally {
			busy = false;
		}
	}

	function close() {
		if (busy) return;
		onClose();
	}
</script>

{#if open}
	<div class="overlay" role="dialog" aria-modal="true" aria-label="Hapus Siswa" onclick={close}>
		<div class="dialog" onclick={(e) => e.stopPropagation()}>
			<header class="dialog-header">
				<h2>Hapus {count} Siswa</h2>
				<button class="btn-icon" onclick={close} title="Tutup" aria-label="Tutup">&times;</button>
			</header>

			<div class="dialog-body">
				<div class="names">
					{#each previewNames as name}
						<span class="chip">{name}</span>
					{/each}
					{#if extra > 0}
						<span class="chip muted">+{extra} lainnya</span>
					{/if}
				</div>

				<div class="warning">
					<p><strong>Peringatan:</strong> akun siswa, token, dan seluruh progress akan
						<strong>dihapus permanen</strong> dan tidak dapat dipulihkan.</p>
					<p>Pastikan Anda sudah <strong>Export CSV</strong> terlebih dahulu agar data dapat
						dibuat ulang nanti.</p>
				</div>

				{#if error}
					<p class="error">{error}</p>
				{/if}
			</div>

			<footer class="dialog-footer">
				<button class="btn" onclick={close} disabled={busy}>Batal</button>
				<button class="btn btn-danger" onclick={handleDelete} disabled={busy || count === 0}>
					{busy ? 'Menghapus…' : 'Hapus Permanen'}
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
		width: min(480px, 100%);
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
	.names {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-bottom: 1rem;
	}
	.chip {
		background: var(--color-bg-secondary);
		border: 1px solid var(--color-border);
		border-radius: 999px;
		padding: 0.25rem 0.7rem;
		font-size: 0.82rem;
	}
	.chip.muted {
		color: var(--color-text-muted);
	}
	.warning {
		border: 1px solid var(--color-danger);
		border-radius: var(--radius);
		background: color-mix(in srgb, var(--color-danger) 8%, var(--color-bg));
		padding: 0.8rem 0.9rem;
		font-size: 0.85rem;
	}
	.warning p {
		margin: 0 0 0.4rem;
	}
	.warning p:last-child {
		margin-bottom: 0;
		color: var(--color-text-muted);
	}
	.error {
		margin-top: 0.9rem;
		color: var(--color-danger);
		font-size: 0.85rem;
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
