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
const LAST_ACTIVE_KEY = 'student_last_active';
const MAX_INACTIVITY = 24 * 60 * 60 * 1000; // 1 day in ms

export const authToken = writable('');
export const authStudentName = writable('');
export const authLoggedIn = writable(false);
export const authIsTeacher = writable(false);

function clearAllCookies() {
	if (typeof document === 'undefined') return;
	const cookies = document.cookie.split(';');
	for (let i = 0; i < cookies.length; i++) {
		const cookie = cookies[i];
		const eqPos = cookie.indexOf('=');
		const name = eqPos > -1 ? cookie.substr(0, eqPos).trim() : cookie.trim();
		document.cookie = name + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/';
	}
}

function clearAuthData() {
	clearAllCookies();
	localStorage.removeItem(STORAGE_KEY);
	localStorage.removeItem(LAST_ACTIVE_KEY);
	sessionStorage.clear();
}

function updateLastActive() {
	if (typeof window !== 'undefined') {
		localStorage.setItem(LAST_ACTIVE_KEY, Date.now().toString());
	}
}

export const auth = {
	/** Current token value (non-reactive). */
	get token() { return get(authToken); },
	get isLoggedIn() { return get(authLoggedIn); },

	/** Restore session from localStorage on app mount. */
	async init() {
		if (typeof window === 'undefined') return;
		
		const saved = localStorage.getItem(STORAGE_KEY);
		const lastActive = localStorage.getItem(LAST_ACTIVE_KEY);

		if (!saved) return;

		// Check for 1 day inactivity
		if (lastActive) {
			const inactiveTime = Date.now() - parseInt(lastActive, 10);
			if (inactiveTime > MAX_INACTIVITY) {
				clearAuthData();
				return;
			}
		}

		try {
			const res = await validateToken(saved);
			if (res.success && res.student_name) {
				authToken.set(saved);
				authStudentName.set(res.student_name);
				authLoggedIn.set(true);
				authIsTeacher.set(res.is_teacher ?? false);
				updateLastActive();
			} else {
				clearAuthData();
			}
		} catch {
			clearAuthData();
		}
	},

	async login(inputToken: string) {
		clearAuthData();

		const res = await apiLogin(inputToken);
		if (res.success && res.student_name) {
			authToken.set(inputToken);
			authStudentName.set(res.student_name);
			authLoggedIn.set(true);
			authIsTeacher.set(res.is_teacher ?? false);
			localStorage.setItem(STORAGE_KEY, inputToken);
			updateLastActive();
		}
		return res;
	},

	async logout() {
		try {
			await apiLogout();
		} catch {
			// ignore logout failure, proceed to clear local state
		}
		authToken.set('');
		authStudentName.set('');
		authLoggedIn.set(false);
		authIsTeacher.set(false);
		clearAuthData();
		location.reload();
	},

	/** Update activity timestamp. Call this on user interactions. */
	recordActivity() {
		if (get(authLoggedIn)) {
			updateLastActive();
		}
	}
};
