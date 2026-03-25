/**
 * Dark / light theme state using Svelte writable store.
 *
 * Usage in .svelte files:
 *   import { themeDark, theme } from '$stores/theme';
 *   // Use $themeDark for reactive boolean
 *   // Use theme.init(), theme.toggle() for actions
 */

import { writable, get } from 'svelte/store';

const STORAGE_KEY = 'theme';

export const themeDark = writable(false);

function apply() {
	if (typeof document === 'undefined') return;
	document.documentElement.setAttribute('data-theme', get(themeDark) ? 'dark' : 'light');
}

export const theme = {
	get isDark() { return get(themeDark); },

	init() {
		if (typeof window === 'undefined') return;
		const saved = localStorage.getItem(STORAGE_KEY);
		if (saved) {
			themeDark.set(saved === 'dark');
		} else {
			themeDark.set(window.matchMedia('(prefers-color-scheme: dark)').matches);
		}
		apply();
	},

	toggle() {
		themeDark.update(d => !d);
		const current = get(themeDark);
		localStorage.setItem(STORAGE_KEY, current ? 'dark' : 'light');
		apply();
	}
};
