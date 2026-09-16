import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SyncManager } from './sync-manager';
import * as schemaModule from './schema';

describe('SyncManager', () => {
	let syncManager: SyncManager;
	let mockMyProgress: Map<string, any>;
	let mockOutbox: Array<any>;
	let mockQuizAttempts: Array<any>;

	beforeEach(() => {
		mockMyProgress = new Map();
		mockOutbox = [];
		mockQuizAttempts = [];

		const mockDb = {
			myProgress: {
				put: vi.fn(async (item) => {
					mockMyProgress.set(item.lessonSlug, item);
					return item.lessonSlug;
				}),
				get: vi.fn(async (slug) => {
					return mockMyProgress.get(slug) || undefined;
				}),
				toArray: vi.fn(async () => {
					return Array.from(mockMyProgress.values());
				}),
				update: vi.fn(async (slug, updates) => {
					const existing = mockMyProgress.get(slug);
					if (existing) {
						mockMyProgress.set(slug, { ...existing, ...updates });
					}
				})
			},
			outbox: {
				add: vi.fn(async (entry) => {
					const id = mockOutbox.length + 1;
					const item = { ...entry, id };
					mockOutbox.push(item);
					return id;
				}),
				orderBy: vi.fn(() => ({
					toArray: vi.fn(async () => [...mockOutbox])
				})),
				delete: vi.fn(async (id) => {
					const idx = mockOutbox.findIndex((e) => e.id === id);
					if (idx >= 0) mockOutbox.splice(idx, 1);
				}),
				update: vi.fn(async (id, updates) => {
					const item = mockOutbox.find((e) => e.id === id);
					if (item) Object.assign(item, updates);
				})
			},
			myQuizAttempts: {
				add: vi.fn(async (item) => {
					mockQuizAttempts.push(item);
					return mockQuizAttempts.length;
				})
			},
			myCodeDrafts: {
				where: vi.fn(() => ({
					first: vi.fn(async () => null)
				})),
				add: vi.fn()
			}
		};

		vi.spyOn(schemaModule, 'db', 'get').mockReturnValue(mockDb as any);

		syncManager = new SyncManager();
	});

	it('records progress locally and enqueues sync to /lesson-progress when authenticated', async () => {
		await syncManager.recordProgress('variabel', true, {
			token: 'student-tok-1',
			lesson_name: 'variabel',
			type: 'exercise'
		});

		const rec = await syncManager.getProgress('variabel');
		expect(rec).not.toBeNull();
		expect(rec?.lessonSlug).toBe('variabel');
		expect(rec?.completed).toBe(true);
		expect(rec?.synced).toBe(false);

		expect(mockOutbox.length).toBe(1);
		expect(mockOutbox[0].endpoint).toBe('/lesson-progress');
		expect(mockOutbox[0].payload.token).toBe('student-tok-1');
	});

	it('records progress locally without enqueueing outbox in guest mode', async () => {
		await syncManager.recordProgress('percabangan', true, null);

		const rec = await syncManager.getProgress('percabangan');
		expect(rec).not.toBeNull();
		expect(rec?.lessonSlug).toBe('percabangan');
		expect(rec?.completed).toBe(true);

		expect(mockOutbox.length).toBe(0);
	});

	it('returns all completed lessons map with getAllProgress', async () => {
		await syncManager.recordProgress('lesson_a', true);
		await syncManager.recordProgress('lesson_b', false);
		await syncManager.recordProgress('lesson_c', true);

		const map = await syncManager.getAllProgress();
		expect(map).toEqual({
			lesson_a: true,
			lesson_b: false,
			lesson_c: true
		});
	});

	it('records quiz attempt and enqueues sync to /lesson-progress', async () => {
		await syncManager.recordQuizAttempt(
			{
				lessonSlug: 'quiz_test',
				attemptId: 'attempt-uuid-1',
				answers: {},
				score: 100,
				startedAt: new Date().toISOString(),
				finishedAt: new Date().toISOString()
			},
			{ token: 'student-tok-1', lesson_name: 'quiz_test', type: 'quiz' }
		);

		expect(mockQuizAttempts.length).toBe(1);
		expect(mockOutbox.length).toBe(1);
		expect(mockOutbox[0].endpoint).toBe('/lesson-progress');
		expect(mockOutbox[0].payload.lesson_name).toBe('quiz_test');
	});

	it('drains outbox queue to /api/lesson-progress and marks progress synced', async () => {
		await syncManager.recordProgress('loop_test', true, {
			token: 'tok-1',
			lesson_name: 'loop_test',
			type: 'exercise'
		});
		expect(mockOutbox.length).toBe(1);

		const fetchMock = vi.fn(async () => ({
			ok: true,
			status: 200,
			json: async () => ({ success: true, is_done: true })
		}));
		(global as any).fetch = fetchMock;
		Object.defineProperty(globalThis.navigator, 'onLine', { value: true, configurable: true });

		await syncManager.drainQueue();

		expect(fetchMock).toHaveBeenCalledWith(
			'/api/lesson-progress',
			expect.objectContaining({
				method: 'POST'
			})
		);
		expect(mockOutbox.length).toBe(0);

		const progress = await syncManager.getProgress('loop_test');
		expect(progress?.synced).toBe(true);
	});
});
