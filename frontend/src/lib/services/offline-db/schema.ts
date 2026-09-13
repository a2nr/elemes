import Dexie, { type Table } from 'dexie';

export interface MyProgress {
	lessonSlug: string;
	completed: boolean;
	completedAt?: string;
	synced: boolean;
}

export interface MyQuizAttempt {
	id?: number;
	lessonSlug: string;
	attemptId: string;
	answers: Record<string, any>;
	score: number;
	startedAt: string;
	finishedAt: string;
	synced: boolean;
}

export interface MyCodeDraft {
	id?: number;
	lessonSlug: string;
	language: 'c' | 'python';
	code: string;
	updatedAt: number;
}

export interface OutboxEntry {
	id?: number;
	endpoint: string;
	method: 'POST' | 'PUT';
	payload: any;
	idempotencyKey: string;
	createdAt: number;
	retries: number;
}

export interface LessonCache {
	slug: string;
	data: any;
	cachedAt: number;
}

export class ElemesMirrorDB extends Dexie {
	myProgress!: Table<MyProgress>;
	myQuizAttempts!: Table<MyQuizAttempt>;
	myCodeDrafts!: Table<MyCodeDraft>;
	outbox!: Table<OutboxEntry>;
	lessonCache!: Table<LessonCache>;

	constructor() {
		super('ElemesMirrorDB');
		this.version(1).stores({
			myProgress: 'lessonSlug, synced',
			myQuizAttempts: '++id, lessonSlug, attemptId, synced',
			myCodeDrafts: '++id, [lessonSlug+language]',
			outbox: '++id, endpoint, createdAt',
			lessonCache: 'slug, cachedAt'
		});
	}
}

export const db = typeof window !== 'undefined' ? new ElemesMirrorDB() : (null as unknown as ElemesMirrorDB);
