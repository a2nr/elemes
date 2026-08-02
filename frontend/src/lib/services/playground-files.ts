/**
 * Validasi nama file untuk file tree playground (C/Python).
 *
 * Terpisah dari komponen agar bisa diuji unit tanpa DOM.
 */

export type PlaygroundLanguage = 'c' | 'python';

export const EXTENSIONS: Record<PlaygroundLanguage, readonly string[]> = {
	c: ['.c', '.h'],
	python: ['.py']
};

export type FileNameResult =
	| { ok: true; name: string }
	| { ok: false; reason: string };

const CONTROL_CHARS = /[\u0000-\u001f\u007f]/;
const FORBIDDEN_CHARS = /[\\/]/;

/** Ekstensi dari nama file (lowercase, termasuk titik). */
export function getExtension(name: string): string {
	const base = name.split(/[\\/]/).pop() ?? name;
	const idx = base.lastIndexOf('.');
	if (idx <= 0) return ''; // nama tanpa titik atau nama tersembunyi (.gitignore)
	return base.slice(idx).toLowerCase();
}

export function languageFromName(name: string): PlaygroundLanguage {
	return getExtension(name) === '.py' ? 'python' : 'c';
}

export function isAllowedExtension(name: string, language: PlaygroundLanguage): boolean {
	return EXTENSIONS[language].includes(getExtension(name));
}

/**
 * Validasi nama file baru / rename.
 * - Hanya basename (tolak slash/backslash)
 * - Tolak ".", "..", nama kosong, karakter kontrol
 * - Tolak duplikat (case-insensitive) terhadap daftar existing
 * - Ekstensi harus valid untuk bahasa
 *
 * @param existingNames daftar nama file lain (tidak termasuk file yang sedang di-rename)
 */
export function validateFileName(
	rawName: string,
	language: PlaygroundLanguage,
	existingNames: string[] = []
): FileNameResult {
	const name = rawName.trim();
	if (!name) {
		return { ok: false, reason: 'Nama file tidak boleh kosong' };
	}
	if (name === '.' || name === '..') {
		return { ok: false, reason: 'Nama file tidak valid' };
	}
	if (FORBIDDEN_CHARS.test(name)) {
		return { ok: false, reason: 'Nama file tidak boleh mengandung / atau \\' };
	}
	if (CONTROL_CHARS.test(name)) {
		return { ok: false, reason: 'Nama file mengandung karakter yang tidak diizinkan' };
	}
	if (name.length > 120) {
		return { ok: false, reason: 'Nama file terlalu panjang' };
	}
	if (!isAllowedExtension(name, language)) {
		const allowed = EXTENSIONS[language].join(' / ');
		return {
			ok: false,
			reason:
				language === 'python'
					? 'File Python harus berekstensi .py'
					: `File C harus berekstensi ${allowed}`
		};
	}
	const lower = name.toLowerCase();
	if (existingNames.some((n) => n.toLowerCase() === lower)) {
		return { ok: false, reason: `File "${name}" sudah ada` };
	}
	return { ok: true, name };
}

/**
 * Buat nama file default unik, mis. "untitled.c", "untitled-2.c", dst.
 */
export function uniqueDefaultName(
	base: string,
	language: PlaygroundLanguage,
	existingNames: string[]
): string {
	const ext = EXTENSIONS[language][0];
	const lowerSet = new Set(existingNames.map((n) => n.toLowerCase()));
	if (!lowerSet.has((base + ext).toLowerCase())) return base + ext;
	let i = 2;
	while (lowerSet.has(`${base}-${i}${ext}`.toLowerCase())) {
		i += 1;
	}
	return `${base}-${i}${ext}`;
}
