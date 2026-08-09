/**
 * Student selection store — halaman progress.
 *
 * Selection disimpan berdasarkan UUID siswa (bukan index/nama) supaya tetap
 * benar setelah data reload/reorder. `setAvailable()` juga mem-prune ID yang
 * sudah tidak ada (stale selection).
 */

import { derived, get, writable } from 'svelte/store';

function createStudentSelection() {
	const available = writable<string[]>([]);
	const selected = writable<string[]>([]);

	/** Set daftar UUID siswa yang ada pada data terakhir; prune selection stale. */
	function setAvailable(ids: string[]) {
		available.set(ids);
		selected.update((list) => list.filter((id) => ids.includes(id)));
	}

	function toggle(uuid: string) {
		selected.update((list) =>
			list.includes(uuid) ? list.filter((x) => x !== uuid) : [...list, uuid]
		);
	}

	function selectAll() {
		selected.set([...get(available)]);
	}

	function clear() {
		selected.set([]);
	}

	/** Semua siswa terpilih (checkbox header check penuh). */
	const allSelected = derived(
		[available, selected],
		([avail, sel]) => avail.length > 0 && avail.every((id) => sel.includes(id))
	);

	/** Sebagian terpilih (checkbox header indeterminate). */
	const someSelected = derived(
		[available, selected],
		([avail, sel]) => sel.some((id) => avail.includes(id))
	);

	/** Jumlah UUID yang sedang dipilih. */
	const count = derived(selected, (s) => s.length);

	return {
		available,
		selected,
		setAvailable,
		toggle,
		selectAll,
		clear,
		allSelected,
		someSelected,
		count
	};
}

export const studentSelection = createStudentSelection();
