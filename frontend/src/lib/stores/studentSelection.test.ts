import { beforeEach, describe, expect, it } from 'vitest';
import { get } from 'svelte/store';
import { studentSelection } from './studentSelection';

const UUID_A = '11111111-1111-4111-8111-111111111111';
const UUID_B = '22222222-2222-4222-8222-222222222222';
const UUID_C = '33333333-3333-4333-8333-333333333333';
const UUID_D = '44444444-4444-4444-8444-444444444444';

describe('studentSelection', () => {
	beforeEach(() => {
		studentSelection.setAvailable([]);
		studentSelection.clear();
	});

	it('toggle menambah dan menghapus selection berdasarkan UUID', () => {
		studentSelection.setAvailable([UUID_A, UUID_B]);
		studentSelection.toggle(UUID_A);
		expect(get(studentSelection.selected)).toEqual([UUID_A]);

		studentSelection.toggle(UUID_A);
		expect(get(studentSelection.selected)).toEqual([]);
	});

	it('select-all memilih semua siswa; clear mengosongkan', () => {
		studentSelection.setAvailable([UUID_A, UUID_B, UUID_C]);
		studentSelection.selectAll();
		expect(get(studentSelection.count)).toBe(3);

		studentSelection.clear();
		expect(get(studentSelection.count)).toBe(0);
	});

	it('allSelected true hanya bila semua available terpilih', () => {
		studentSelection.setAvailable([UUID_A, UUID_B]);
		studentSelection.toggle(UUID_A);
		expect(get(studentSelection.allSelected)).toBe(false);

		studentSelection.toggle(UUID_B);
		expect(get(studentSelection.allSelected)).toBe(true);
	});

	it('someSelected / indeterminate saat sebagian terpilih', () => {
		studentSelection.setAvailable([UUID_A, UUID_B]);
		expect(get(studentSelection.someSelected)).toBe(false);

		studentSelection.toggle(UUID_A);
		expect(get(studentSelection.someSelected)).toBe(true);
		expect(get(studentSelection.allSelected)).toBe(false);

		studentSelection.toggle(UUID_B);
		expect(get(studentSelection.someSelected)).toBe(true);
		expect(get(studentSelection.allSelected)).toBe(true);
	});

	it('allSelected false saat available kosong', () => {
		studentSelection.setAvailable([]);
		expect(get(studentSelection.allSelected)).toBe(false);
	});

	it('setAvailable mem-prune selection stale setelah data reload', () => {
		studentSelection.setAvailable([UUID_A, UUID_B, UUID_C]);
		studentSelection.toggle(UUID_A);
		studentSelection.toggle(UUID_C);

		// reload: siswa B & C hilang, muncul UUID baru
		studentSelection.setAvailable([UUID_A, UUID_D]);
		expect(get(studentSelection.selected)).toEqual([UUID_A]);
		expect(get(studentSelection.count)).toBe(1);
	});

	it('selection berbasis UUID tidak bergeser saat data di-reorder', () => {
		studentSelection.setAvailable([UUID_A, UUID_B, UUID_C]);
		studentSelection.toggle(UUID_B);

		// urutan data berubah → selection tetap pada UUID yang sama
		studentSelection.setAvailable([UUID_C, UUID_B, UUID_A]);
		expect(get(studentSelection.selected)).toEqual([UUID_B]);
	});

	it('setAvailable membersihkan ID yang tidak ada di available', () => {
		studentSelection.setAvailable([UUID_A, UUID_B]);
		studentSelection.toggle(UUID_A);
		studentSelection.toggle(UUID_B);
		studentSelection.setAvailable([UUID_A]);
		expect(get(studentSelection.selected)).toEqual([UUID_A]);
	});
});
