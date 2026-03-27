/**
 * Shared authentication state using Svelte writable stores.
 *
 * Usage in .svelte files:
 *   import { authToken, authStudentName, authLoggedIn, auth } from '$stores/auth';
 *   // Use $authLoggedIn, $authStudentName, $authToken for reactive values
 *   // Use auth.init(), auth.login(), auth.logout() for actions
 */

import { writable, get } from 'svelte/store';
import { validateToken, login as apiLogin, logout as apiLogout } from '$services/api';

const STORAGE_KEY = 'student_token';

export const authToken = writable('');
export const authStudentName = writable('');
export const authLoggedIn = writable(false);
export const authIsTeacher = writable(false);

export const auth = {
	/** Current token value (non-reactive). */
	get token() { return get(authToken); },
	get isLoggedIn() { return get(authLoggedIn); },

	/** Restore session from localStorage on app mount. */
	async init() {
		if (typeof window === 'undefined') return;
		const saved = localStorage.getItem(STORAGE_KEY);
		if (!saved) return;

		try {
			const res = await validateToken(saved);
			if (res.success && res.student_name) {
				authToken.set(saved);
				authStudentName.set(res.student_name);
				authLoggedIn.set(true);
				authIsTeacher.set(res.is_teacher ?? false);
			} else {
				localStorage.removeItem(STORAGE_KEY);
				sessionStorage.clear();
			}
		} catch {
			localStorage.removeItem(STORAGE_KEY);
			sessionStorage.clear();
		}
	},

	async login(inputToken: string) {
		const res = await apiLogin(inputToken);
		if (res.success && res.student_name) {
			authToken.set(inputToken);
			authStudentName.set(res.student_name);
			authLoggedIn.set(true);
			authIsTeacher.set(res.is_teacher ?? false);
			localStorage.setItem(STORAGE_KEY, inputToken);
			sessionStorage.clear();
		}
		return res;
	},

	async logout() {
		await apiLogout();
		authToken.set('');
		authStudentName.set('');
		authLoggedIn.set(false);
		authIsTeacher.set(false);
		localStorage.removeItem(STORAGE_KEY);
		sessionStorage.clear();
	}
};
