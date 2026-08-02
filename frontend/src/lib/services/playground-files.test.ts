import { describe, it, expect } from 'vitest';
import {
	validateFileName,
	uniqueDefaultName,
	isAllowedExtension,
	getExtension,
	languageFromName
} from './playground-files';

describe('getExtension / languageFromName', () => {
	it('mengambil ekstensi lowercase dengan titik', () => {
		expect(getExtension('foo.c')).toBe('.c');
		expect(getExtension('FOO.H')).toBe('.h');
		expect(getExtension('main.py')).toBe('.py');
		expect(getExtension('README')).toBe('');
	});

	it('languageFromName: .py → python, lainnya → c', () => {
		expect(languageFromName('main.py')).toBe('python');
		expect(languageFromName('foo.h')).toBe('c');
		expect(languageFromName('main.c')).toBe('c');
	});
});

describe('isAllowedExtension', () => {
	it('C menerima .c dan .h, menolak .py', () => {
		expect(isAllowedExtension('a.c', 'c')).toBe(true);
		expect(isAllowedExtension('a.h', 'c')).toBe(true);
		expect(isAllowedExtension('a.py', 'c')).toBe(false);
	});

	it('Python menerima .py, menolak .h dan .c', () => {
		expect(isAllowedExtension('a.py', 'python')).toBe(true);
		expect(isAllowedExtension('a.h', 'python')).toBe(false);
		expect(isAllowedExtension('a.c', 'python')).toBe(false);
	});
});

describe('validateFileName', () => {
	it('foo.h diterima di mode C (regresi bug utama)', () => {
		const res = validateFileName('foo.h', 'c', ['main.c']);
		expect(res.ok).toBe(true);
		if (res.ok) expect(res.name).toBe('foo.h');
	});

	it('menolak nama kosong dan whitespace-only', () => {
		expect(validateFileName('', 'c').ok).toBe(false);
		expect(validateFileName('   ', 'c').ok).toBe(false);
	});

	it('menolak traversal path: slash, backslash, ".", ".."', () => {
		expect(validateFileName('../evil.c', 'c').ok).toBe(false);
		expect(validateFileName('dir/evil.c', 'c').ok).toBe(false);
		expect(validateFileName('dir\\evil.c', 'c').ok).toBe(false);
		expect(validateFileName('.', 'c').ok).toBe(false);
		expect(validateFileName('..', 'c').ok).toBe(false);
	});

	it('menolak karakter kontrol', () => {
		expect(validateFileName('a\nb.c', 'c').ok).toBe(false);
	});

	it('menolak duplikat case-insensitive', () => {
		const res = validateFileName('MAIN.C', 'c', ['main.c']);
		expect(res.ok).toBe(false);
		if (!res.ok) expect(res.reason).toContain('sudah ada');
	});

	it('duplikat tidak menolak jika nama berbeda', () => {
		expect(validateFileName('main2.c', 'c', ['main.c']).ok).toBe(true);
	});

	it('Python menolak .h dengan pesan jelas', () => {
		const res = validateFileName('foo.h', 'python');
		expect(res.ok).toBe(false);
		if (!res.ok) expect(res.reason).toContain('.py');
	});

	it('C menolak .py', () => {
		const res = validateFileName('foo.py', 'c');
		expect(res.ok).toBe(false);
		if (!res.ok) expect(res.reason).toContain('.c');
	});

	it('ekstensi tanpa titik ditolak', () => {
		expect(validateFileName('README', 'c').ok).toBe(false);
	});
});

describe('uniqueDefaultName', () => {
	it('mengembalikan base + ekstensi bila bebas', () => {
		expect(uniqueDefaultName('untitled', 'c', ['main.c'])).toBe('untitled.c');
		expect(uniqueDefaultName('untitled', 'python', ['main.py'])).toBe('untitled.py');
	});

	it('menambah angka bila nama sudah dipakai', () => {
		expect(uniqueDefaultName('untitled', 'c', ['main.c', 'untitled.c'])).toBe('untitled-2.c');
	});

	it('menghindari celah penomoran', () => {
		expect(uniqueDefaultName('untitled', 'c', ['untitled.c', 'untitled-2.c'])).toBe(
			'untitled-3.c'
		);
	});

	it('case-insensitive terhadap existing', () => {
		expect(uniqueDefaultName('untitled', 'c', ['UNTITLED.C'])).toBe('untitled-2.c');
	});
});
