<script lang="ts">
	import { addStudent } from '$services/studentManagement';

	interface Props {
		open: boolean;
		onClose: () => void;
		onAdded: () => void;
	}

	let { open, onClose, onAdded }: Props = $props();

	let namaSiswa = $state('');
	let token = $state('');
	let busy = $state(false);
	let error = $state('');
	let added = $state(false);
	let addedName = $state('');

	const canSubmit = $derived(namaSiswa.trim().length > 0 && token.trim().length >= 8 && !busy && !added);

	async function handleSubmit() {
		if (busy || added) return;
		busy = true;
		error = '';
		try {
			const res = await addStudent(namaSiswa.trim(), token);
			if (res.success) {
				added = true;
				addedName = res.nama_siswa ?? namaSiswa.trim();
				onAdded();
			} else {
				error = res.message ?? 'Gagal menambahkan siswa.';
				if (res.errors?.length) {
					error += '\n' + res.errors.slice(0, 5).join('\n');
				}
			}
		} catch (e) {
			error =
				e instanceof Error && e.message
					? e.message
					: 'Terjadi kesalahan saat menambahkan siswa.';
		} finally {
			busy = false;
		}
	}

	function close() {
		if (busy) return;
		onClose();
	}

	function reset() {
		namaSiswa = '';
		token = '';
		error = '';
		added = false;
		addedName = '';
	}

	// Reset state setiap kali dialog dibuka ulang
	$effect(() => {
		if (open) reset();
	});
</script>

{#if open}
	<div class="overlay" role="dialog" aria-modal="true" aria-label="Tambah Siswa" onclick={close}>
		<div class="dialog" onclick={(e) => e.stopPropagation()}>
			<header class="dialog-header">
				<h2>Tambah Siswa</h2>
				<button class="btn-icon" onclick={close} title="Tutup" aria-label="Tutup">&times;</button>
			</header>

			<div class="dialog-body">
				{#if added}
					<p class="status success">Siswa <strong>{addedName}</strong> berhasil ditambahkan!</p>
				{:else}
					<p class="hint">
						Isi nama siswa dan token unik. Token digunakan siswa untuk login — panjang
						<strong>8–128 karakter</strong>, tanpa spasi/karakter kontrol.
					</p>

					<label class="field">
						<span>Nama Siswa</span>
						<input
							type="text"
							bind:value={namaSiswa}
							placeholder="Mis. Andi Wijaya"
							disabled={busy}
							autocomplete="off"
						/>
					</label>

					<label class="field">
						<span>Token</span>
						<input
							type="text"
							bind:value={token}
							placeholder="Mis. TOKEN_ANDI_001"
							disabled={busy}
							autocomplete="off"
						/>
						<small class="field-hint">8–128 karakter, tanpa spasi/karakter kontrol.</small>
					</label>

					{#if error}
						<p class="error">{error}</p>
					{/if}
				{/if}
			</div>

			<footer class="dialog-footer">
				<button class="btn" onclick={close} disabled={busy}>Batal</button>
				{#if added}
					<button class="btn btn-primary" onclick={close}>Tutup</button>
				{:else}
					<button class="btn btn-primary" onclick={handleSubmit} disabled={!canSubmit}>
						{busy ? 'Menyimpan…' : 'Tambah Siswa'}
					</button>
				{/if}
			</footer>
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.45);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}
	.dialog {
		background: var(--color-bg);
		border-radius: var(--radius);
		width: 100%;
		max-width: 420px;
		box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
	.dialog-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.9rem 1.1rem;
		border-bottom: 1px solid var(--color-border);
	}
	.dialog-header h2 {
		margin: 0;
		font-size: 1.1rem;
	}
	.btn-icon {
		background: none;
		border: none;
		font-size: 1.4rem;
		line-height: 1;
		cursor: pointer;
		color: var(--color-text-muted);
	}
	.btn-icon:hover {
		color: var(--color-text);
	}
	.dialog-body {
		padding: 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}
	.hint {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		line-height: 1.5;
		margin: 0;
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-size: 0.85rem;
		font-weight: 600;
	}
	.field input {
		padding: 0.55rem 0.7rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		font-size: 0.95rem;
		font-weight: 400;
		background: var(--color-bg);
		color: var(--color-text);
	}
	.field input:focus {
		outline: none;
		border-color: var(--color-primary);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-primary) 20%, transparent);
	}
	.field-hint {
		font-size: 0.75rem;
		font-weight: 400;
		color: var(--color-text-muted);
	}
	.status.success {
		color: var(--color-success);
		background: color-mix(in srgb, var(--color-success) 10%, var(--color-bg));
		border: 1px solid color-mix(in srgb, var(--color-success) 40%, var(--color-bg));
		border-radius: var(--radius);
		padding: 0.7rem 0.9rem;
		font-size: 0.9rem;
		margin: 0;
	}
	.error {
		color: var(--color-danger);
		font-size: 0.85rem;
		white-space: pre-line;
		background: color-mix(in srgb, var(--color-danger) 8%, var(--color-bg));
		padding: 0.6rem 0.8rem;
		border-radius: var(--radius);
		border: 1px solid var(--color-danger);
		margin: 0;
	}
	.dialog-footer {
		display: flex;
		justify-content: flex-end;
		gap: 0.6rem;
		padding: 0.9rem 1.1rem;
		border-top: 1px solid var(--color-border);
	}
	.btn {
		padding: 0.5rem 1.1rem;
		border-radius: var(--radius);
		font-weight: 600;
		cursor: pointer;
		border: 1px solid var(--color-border);
		background: var(--color-bg);
		color: var(--color-text);
	}
	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.btn-primary {
		background: var(--color-primary);
		border-color: var(--color-primary);
		color: #fff;
	}
	.btn-primary:hover:not(:disabled) {
		background: var(--color-primary-dark, var(--color-primary));
	}
</style>
