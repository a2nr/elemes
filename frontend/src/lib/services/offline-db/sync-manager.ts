import { db, type MyCodeDraft, type MyProgress, type MyQuizAttempt } from './schema';

export class SyncManager {
	private heartbeatId: ReturnType<typeof setInterval> | null = null;
	private isDraining = false;

	start(): void {
		if (typeof window === 'undefined') return;

		window.addEventListener('online', () => {
			this.drainQueue();
		});

		this.heartbeatId = setInterval(() => {
			if (navigator.onLine) {
				this.drainQueue();
			}
		}, 30_000);

		// Initial drain on startup/login
		if (navigator.onLine) {
			this.drainQueue();
		}
	}

	stop(): void {
		if (this.heartbeatId) {
			clearInterval(this.heartbeatId);
			this.heartbeatId = null;
		}
	}

	/**
	 * Save progress in local IndexedDB mirror immediately,
	 * then opportunistically sync to server if authenticated payload is provided.
	 */
	async recordProgress(lessonSlug: string, completed: boolean, payload?: any): Promise<void> {
		if (!db) return;

		const progress: MyProgress = {
			lessonSlug,
			completed,
			completedAt: new Date().toISOString(),
			synced: false
		};
		await db.myProgress.put(progress);

		if (payload && payload.token) {
			await this.enqueueAndTrySync('/lesson-progress', payload);
		}
	}

	/**
	 * Get progress for a specific lesson from local IndexedDB mirror.
	 */
	async getProgress(lessonSlug: string): Promise<MyProgress | null> {
		if (!db) return null;
		const record = await db.myProgress.get(lessonSlug);
		return record ?? null;
	}

	/**
	 * Get all recorded completed lesson slugs from local IndexedDB mirror.
	 */
	async getAllProgress(): Promise<Record<string, boolean>> {
		if (!db) return {};
		const all = await db.myProgress.toArray();
		const map: Record<string, boolean> = {};
		for (const item of all) {
			map[item.lessonSlug] = item.completed;
		}
		return map;
	}

	/**
	 * Record a completed quiz attempt locally, then sync.
	 */
	async recordQuizAttempt(attempt: Omit<MyQuizAttempt, 'id' | 'synced'>, syncPayload?: any): Promise<void> {
		if (!db) return;

		await db.myQuizAttempts.add({
			...attempt,
			synced: false
		});

		if (syncPayload && syncPayload.token) {
			await this.enqueueAndTrySync('/lesson-progress', syncPayload);
		}
	}

	/**
	 * Auto-save code draft locally
	 */
	async saveCodeDraft(lessonSlug: string, language: 'c' | 'python', code: string): Promise<void> {
		if (!db) return;

		const existing = await db.myCodeDrafts.where({ lessonSlug, language }).first();
		if (existing && existing.id) {
			await db.myCodeDrafts.update(existing.id, { code, updatedAt: Date.now() });
		} else {
			await db.myCodeDrafts.add({
				lessonSlug,
				language,
				code,
				updatedAt: Date.now()
			});
		}
	}

	/**
	 * Load code draft from local DB
	 */
	async loadCodeDraft(lessonSlug: string, language: 'c' | 'python'): Promise<string | null> {
		if (!db) return null;
		const draft = await db.myCodeDrafts.where({ lessonSlug, language }).first();
		return draft ? draft.code : null;
	}

	/**
	 * Enqueue mutation in outbox and try sending immediately if online
	 */
	async enqueueAndTrySync(endpoint: string, payload: any, method: 'POST' | 'PUT' = 'POST'): Promise<void> {
		if (!db) return;

		const entry = {
			endpoint,
			method,
			payload,
			idempotencyKey: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2),
			createdAt: Date.now(),
			retries: 0
		};

		await db.outbox.add(entry);

		if (typeof navigator !== 'undefined' && navigator.onLine) {
			await this.drainQueue();
		}
	}

	async drainQueue(): Promise<void> {
		if (!db || this.isDraining || (typeof navigator !== 'undefined' && !navigator.onLine)) {
			return;
		}

		this.isDraining = true;
		try {
			const pending = await db.outbox.orderBy('createdAt').toArray();
			for (const entry of pending) {
				try {
					const res = await fetch(`/api${entry.endpoint}`, {
						method: entry.method,
						headers: {
							'Content-Type': 'application/json',
							'X-Idempotency-Key': entry.idempotencyKey
						},
						body: JSON.stringify(entry.payload)
					});

					if (res.ok) {
						if (entry.id) {
							await db.outbox.delete(entry.id);
						}
						if (entry.payload?.lesson_name) {
							await db.myProgress.update(entry.payload.lesson_name, { synced: true }).catch(() => {});
						}
					} else if (entry.retries < 5 && entry.id) {
						await db.outbox.update(entry.id, { retries: entry.retries + 1 });
					}
				} catch {
					// Network failed or offline - remain in queue for next sync
					break;
				}
			}
		} finally {
			this.isDraining = false;
		}
	}
}

export const syncManager = new SyncManager();
