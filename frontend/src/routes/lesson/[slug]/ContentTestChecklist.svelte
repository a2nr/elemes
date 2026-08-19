<script lang="ts">
	import { detectContentFeatures, type ContentFeature, type ContentFeatureId } from '$services/content-features';
	import type { LessonManager } from './lesson.svelte';

	interface Props {
		mgr: LessonManager;
	}

	let { mgr }: Props = $props();

	const features = $derived(detectContentFeatures(mgr.data?.quiz_data));

	// Manual checklist items — toggled by teacher click, not persisted
	let manualChecks = $state<Record<string, boolean>>({});

	// Anti-cheat items — always shown
	interface AntiCheatItem {
		id: string;
		label: string;
		autoVerified: boolean;
	}

	const flashcardAutoVerified = $derived(() => {
		if (!mgr.quizSession) return false;
		const questions = mgr.quizSession.questions;
		for (const q of questions) {
			if (q.type === 'flashcard') {
				const answer = mgr.quizSession.answers[q.id];
				if (answer?.understood !== undefined) return true;
			}
		}
		return false;
	});

	const focusLostVerified = $derived(mgr.quizTerminationReason === 'focus_lost');

	const antiCheatItems = $derived<AntiCheatItem[]>([
		{
			id: 'focus_lost',
			label: 'Anti-cheat: focus_lost teruji (tab switch / minimize)',
			autoVerified: focusLostVerified
		},
		{
			id: 'page_unload',
			label: 'Anti-cheat: page_unload teruji (refresh / close tab)',
			autoVerified: false // Must be verified via GET fetch after reload
		}
	]);

	function toggleManual(id: string) {
		manualChecks[id] = !manualChecks[id];
	}
</script>

{#if features.length > 0 || antiCheatItems.length > 0}
	<div class="content-test-checklist">
		<h4 class="checklist-heading">✅ Checklist Uji Konten</h4>

		<!-- Content-specific features -->
		{#each features as feature (feature.id)}
			{#if feature.verification === 'auto'}
				{@const verified = feature.id === 'flashcard' ? flashcardAutoVerified() : false}
				<label class="checklist-item" class:verified>
					<input type="checkbox" checked={verified} disabled />
					<span class="checklist-label">
						{feature.checklistLabel}
						{#if verified}
							<span class="check-badge auto">✓ auto</span>
						{/if}
					</span>
				</label>
			{:else}
				<label class="checklist-item" class:verified={manualChecks[feature.id]}>
					<input
						type="checkbox"
						checked={manualChecks[feature.id] ?? false}
						onchange={() => toggleManual(feature.id)}
					/>
					<span class="checklist-label">{feature.checklistLabel}</span>
				</label>
			{/if}
		{/each}

		<!-- Anti-cheat items (always shown) -->
		{#each antiCheatItems as item (item.id)}
			<label class="checklist-item" class:verified={item.autoVerified || manualChecks[item.id]}>
				<input
					type="checkbox"
					checked={item.autoVerified || (manualChecks[item.id] ?? false)}
					disabled={item.autoVerified}
					onchange={() => !item.autoVerified && toggleManual(item.id)}
				/>
				<span class="checklist-label">
					{item.label}
					{#if item.autoVerified}
						<span class="check-badge auto">✓ auto</span>
					{/if}
				</span>
			</label>
		{/each}
	</div>
{:else}
	<div class="content-test-checklist empty">
		<p class="checklist-empty-msg">Tidak ada elemen kuis untuk diuji.</p>
	</div>
{/if}

<style>
	.content-test-checklist {
		background: var(--color-bg-secondary, #f8f9fa);
		border: 1px solid var(--color-border, #dee2e6);
		border-radius: 8px;
		padding: 1rem;
		margin-top: 0.75rem;
	}
	.content-test-checklist.empty {
		text-align: center;
		color: var(--color-text-muted, #6c757d);
		padding: 0.75rem;
	}
	.checklist-heading {
		margin: 0 0 0.75rem;
		font-size: 0.95rem;
		color: var(--color-text, #212529);
	}
	.checklist-item {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		padding: 0.35rem 0;
		font-size: 0.85rem;
		line-height: 1.4;
		cursor: pointer;
		transition: opacity 0.15s;
	}
	.checklist-item input[type='checkbox'] {
		margin-top: 2px;
		flex-shrink: 0;
	}
	.checklist-item.verified .checklist-label {
		color: var(--color-success, #198754);
	}
	.checklist-label {
		flex: 1;
	}
	.check-badge {
		display: inline-block;
		font-size: 0.7rem;
		padding: 1px 6px;
		border-radius: 4px;
		margin-left: 0.35rem;
		vertical-align: middle;
		font-weight: 600;
	}
	.check-badge.auto {
		background: rgba(25, 135, 84, 0.12);
		color: var(--color-success, #198754);
	}
	.checklist-empty-msg {
		margin: 0;
		font-size: 0.85rem;
	}
</style>
