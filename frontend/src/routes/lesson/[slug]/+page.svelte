<script lang="ts">
	import './lesson.css';
	import { beforeNavigate } from '$app/navigation';
	import CodeTab from './CodeTab.svelte';
	import CircuitTab from './CircuitTab.svelte';
	import VelxioTab from './VelxioTab.svelte';
	import FlowchartTab from './FlowchartTab.svelte';
	import QuizTab from './QuizTab.svelte';
import QuizQuestionView from './QuizQuestionView.svelte';
	import DeployTab from './DeployTab.svelte';
	import OutputPanel from '$components/OutputPanel.svelte';
	import CelebrationOverlay from '$components/CelebrationOverlay.svelte';
	import WorkspaceHeader from '$components/WorkspaceHeader.svelte';
	import LessonList from '$components/LessonList.svelte';
	import { lessonContext } from '$stores/lessonContext';
	import { noSelect } from '$actions/noSelect';
	import { createFloatingPanel } from '$actions/floatingPanel.svelte';
	import { highlightAllCode } from '$actions/highlightCode';
	import { setupTryButtons } from '$actions/setupTryButtons';
	import { renderCircuitEmbeds } from '$actions/renderCircuitEmbeds';
	import { renderFlowchartEmbeds } from '$actions/renderFlowchartEmbeds';

	import { renderMath, autoRenderMath } from '$lib/actions/renderMath';
	import { tick, mount, unmount, onMount } from 'svelte';
	import { LessonManager } from './lesson.svelte';
	import { ensureActiveTab } from '$services/lesson-tabs';
	import { authLoggedIn, authToken } from '$stores/auth';
	import { get } from 'svelte/store';
	import SlideCarousel from '$components/SlideCarousel.svelte';

	let { data: pageData } = $props();
	const mgr = new LessonManager();
	const float = createFloatingPanel();

	let slideComponent = $state<any>(null);

	// Initialize manager with lesson data whenever it changes.
		$effect(() => {
			if (pageData.lesson) {
				mgr.init(pageData.lesson);
			}
		});

		// Safety-net: whenever lesson data changes, ensure the active tab is valid.
		// This prevents "phantom tab" bugs where activeTab points to a panel that
		// isn't rendered (e.g. 'editor' on a quiz-only lesson), leaving the workspace empty.
		$effect(() => {
			if (pageData.lesson && mgr.data) {
				const validated = ensureActiveTab(mgr.data, mgr.activeTab as any);
				if (validated !== mgr.activeTab) {
					mgr.activeTab = validated as any;
				}
			}
		});

	// Handle Slide Carousel mounting
	$effect(() => {
		const slides = mgr.data?.slides;
		if (slides && slides.length > 0) {
			tick().then(() => {
				const mountPoint = document.getElementById('slide-mount-point');
				if (mountPoint) {
					// Clean up previous if exists
					if (slideComponent) {
						unmount(slideComponent);
						slideComponent = null;
					}
					// Mount new carousel
					slideComponent = mount(SlideCarousel, {
						target: mountPoint,
						props: { slides }
					});
				}
			});
		}
		return () => {
			if (slideComponent) {
				unmount(slideComponent);
				slideComponent = null;
			}
		};
	});

	// Mobile behavior for floating panel
	$effect(() => {
		if (mgr.isMobile) {
			float.floating = false;
			float.minimized = false;
		}
	});

	// Dock editor if lesson is locked
	$effect(() => {
		if (mgr.data?.locked && float.floating) {
			float.floating = false;
			float.minimized = false;
		}
	});

	// Run language sync effect
	mgr.setupLanguageSync();

	// Syntax highlighting and embeds
	$effect(() => {
		if (mgr.data) {
			tick().then(() => {
				const containers = [contentEl, tabsEl].filter(Boolean) as HTMLElement[];
				containers.forEach(el => {
					setupTryButtons(el, (code, lang) => mgr.handleTryCode(code, lang, float));
					highlightAllCode(el);
					renderCircuitEmbeds(el);
					renderFlowchartEmbeds(el);

					autoRenderMath(el);
				});
			});
		}
	});

	// Re-run the render pipeline whenever the active quiz question changes
	$effect(() => {
		const q = mgr.currentQuizQuestion;
		if (mgr.isQuizMode && q) {
			tick().then(() => {
				if (!quizQuestionEl) return;
				highlightAllCode(quizQuestionEl);
				renderCircuitEmbeds(quizQuestionEl);
				renderFlowchartEmbeds(quizQuestionEl);
				autoRenderMath(quizQuestionEl);
			});
		}
	});

	beforeNavigate(() => {
		lessonContext.set(null);

		// Quiz integrity: submit with penalty on SPA navigation
		if (mgr.isQuizMode) {
			mgr.submitQuiz(); // fire-and-forget, async
		}

		if (mgr.velxioCleanup) {
			mgr.velxioCleanup();
			mgr.velxioCleanup = null;
		}
		if (mgr.velxioBridge) {
			mgr.velxioBridge.destroy();
			mgr.velxioBridge = null;
		}
	});

	onMount(() => {
		const handleBeforeUnload = (e: BeforeUnloadEvent) => {
			if (mgr.isQuizMode) {
				// Calculate score with penalty from the session (single source of truth)
				const statusString = mgr.getExitStatus();
				const lessonName = mgr.slug.replace('.md', '');

				// Send beacon to /track-progress (fire-and-forget on page unload)
				const payload = JSON.stringify({
					token: get(authToken) || localStorage.getItem('student_token') || '',
					lesson_name: lessonName,
					status: statusString
				});
				navigator.sendBeacon(
					'/api/track-progress',
					new Blob([payload], { type: 'application/json' })
				);

				// Trigger browser confirm dialog
				e.preventDefault();
				e.returnValue = '';
			}
		};
		window.addEventListener('beforeunload', handleBeforeUnload);
		return () => window.removeEventListener('beforeunload', handleBeforeUnload);
	});

	let contentEl = $state<HTMLElement | null>(null);
	let quizQuestionEl = $state<HTMLElement | null>(null);
	let tabsEl = $state<HTMLElement | null>(null);
</script>

<svelte:head>
	<title>{mgr.data?.lesson_title ?? 'Pelajaran'} - Elemes LMS</title>
</svelte:head>

{#if pageData.lesson}
	{#key mgr.slug}
		<div class="lesson-layout" class:single-col={float.floating || mgr.isMobile}>
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div class="lesson-content" bind:this={contentEl} use:noSelect use:renderMath
				role="region" aria-label="Konten pelajaran"
				class:full-width={float.floating || mgr.isMobile}
				onselectstart={(e) => e.preventDefault()}
				oncopy={(e) => e.preventDefault()}
				oncut={(e) => e.preventDefault()}
				oncontextmenu={(e) => e.preventDefault()}>
				
				{#if mgr.data?.locked}
					<div class="locked-banner">
						<span class="locked-banner-icon">&#128274;</span>
						<div>
							<strong>Pelajaran ini terkunci.</strong> Kamu dapat membaca materinya, namun workspace (editor) dinonaktifkan hingga prasyarat selesai.
							{#if mgr.data.missing_prerequisites?.length}
								<div class="missing-list">
									Belum selesai: 
									{#each mgr.data.missing_prerequisites as p, i}
										<a href="/lesson/{p}" class="prereq-link">{mgr.getLessonTitle(p)}</a>{i < mgr.data.missing_prerequisites.length - 1 ? ', ' : ''}
									{/each}
								</div>
							{/if}
						</div>
					</div>
				{/if}

	{#if mgr.isQuizMode}
		<div class="quiz-question-area" bind:this={quizQuestionEl}>
			<QuizQuestionView
				question={mgr.currentQuizQuestion}
				currentIndex={mgr.quizCurrentIndex}
				totalCount={mgr.quizTotalCount}
				answeredCount={mgr.quizAnsweredCount}
				onExit={() => {
					mgr.submitQuiz();
				}}
			/>
		</div>
	{:else}
		<div class="prose">{@html mgr.data?.lesson_content ?? ''}</div>
		<LessonList lessons={mgr.data?.ordered_lessons ?? []} currentSlug={mgr.slug} />
	{/if}
				</div>

				{#if float.floating && float.minimized && !mgr.isMobile}
				<button type="button" class="float-restore-btn" onclick={float.restore}>&#9654; Editor</button>
				{/if}

				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="editor-area"
				class:floating={float.floating && !mgr.isMobile && !float.minimized}
				class:floating-hidden={float.floating && float.minimized && !mgr.isMobile}
				class:mobile-sheet={mgr.isMobile}
				class:mobile-hidden={mgr.isMobile && mgr.mobileMode === 'hidden'}
				class:mobile-half={mgr.isMobile && mgr.mobileMode === 'half'}
				class:mobile-full={mgr.isMobile && mgr.mobileMode === 'full'}
				class:editor-locked={mgr.data?.locked}
				style={float.style}>

				<WorkspaceHeader
					isMobile={mgr.isMobile}
					bind:mobileMode={mgr.mobileMode}
					bind:activeTab={mgr.activeTab}
					bind:currentLanguage={mgr.currentLanguage}
					hasInfo={!!mgr.data?.lesson_info}
					hasExercise={!!mgr.data?.exercise_content}
					activeTabs={mgr.data?.active_tabs ?? []}
					floating={float.floating}
					minimized={float.minimized}
					onDragStart={float.onDragStart}
					onResizeStart={float.onResizeStart}
					onFloatToggle={float.toggle}
					onMinimize={float.minimize}
					locked={mgr.data?.locked}
				/>

				<div class="editor-body" bind:this={tabsEl} use:renderMath style="position: relative;">
					{#if mgr.data?.locked}
						<div class="workspace-lock-overlay">
							<div class="lock-overlay-content">
								<div class="lock-overlay-icon">&#128274;</div>
								<h3>Workspace Terkunci</h3>
								<p>Selesaikan materi sebelumnya untuk mulai mengerjakan latihan ini.</p>
							</div>
						</div>
					{/if}

					<div class="tab-panel" class:tab-hidden={mgr.activeTab !== 'info'} use:noSelect>
						{#if mgr.data?.lesson_info}
							<div class="tab-content">{@html mgr.data.lesson_info}</div>
						{/if}
					</div>

					<div class="tab-panel" class:tab-hidden={mgr.activeTab !== 'exercise'} use:noSelect>
						{#if mgr.data?.exercise_content}
							<div class="tab-content">
								<h2 class="tab-heading">Latihan</h2>
								{@html mgr.data.exercise_content}
							</div>
						{/if}
					</div>

					{#if mgr.data?.active_tabs?.includes('circuit')}
						<div class="tab-panel" class:tab-hidden={mgr.activeTab !== 'circuit'}>
							<CircuitTab
								data={mgr.data}
								bind:circuitEditor={mgr.circuitEditor}
								compiling={mgr.compiling}
								authLoggedIn={$authLoggedIn}
								lessonCompleted={mgr.lessonCompleted}
								showSolution={mgr.showSolution}
								slug={mgr.slug}
								onRun={mgr.handleRun.bind(mgr)}
								onReset={mgr.handleReset.bind(mgr)}
								onShowSolution={mgr.handleShowSolution.bind(mgr)}
							/>
						</div>
					{/if}

					{#if mgr.isVelxio}
						<div class="tab-panel velxio-panel" class:tab-hidden={mgr.activeTab !== 'velxio'}>
							<VelxioTab
								hasArduinoCode={!!mgr.data?.initial_code_arduino}
								velxioError={mgr.velxioError}
								authLoggedIn={$authLoggedIn}
								velxioSaving={mgr.velxioSaving}
								onSetupBridge={mgr.setupVelxioBridge.bind(mgr)}
							/>
						</div>
					{/if}

					{#if mgr.isFlowchart}
						<div class="tab-panel flowchart-panel" class:tab-hidden={mgr.activeTab !== 'flowchart'}>
							<FlowchartTab
								bind:this={mgr.flowchartTab}
								storageKey={mgr.flowchartStorageKey}
								initialData={mgr.data?.initial_flowchart}
								onRun={mgr.handleRun.bind(mgr)}
								compiling={mgr.compiling}
							/>
						</div>
					{/if}

					{#if mgr.isDeployable}
						<div class="tab-panel" class:tab-hidden={mgr.activeTab !== 'deploy'}>
							<DeployTab
								velxioIframe={mgr.velxioIframe}
								arduinoCodeKey={mgr.arduinoCodeKey}
								slug={mgr.slug}
								authLoggedIn={$authLoggedIn}
							/>
						</div>
					{/if}

					{#if mgr.data && (!mgr.data.active_tabs?.length || mgr.data.active_tabs.includes('c') || mgr.data.active_tabs.includes('python'))}
						<div class="tab-panel" class:tab-hidden={mgr.activeTab !== 'editor'}>
							<CodeTab
								data={mgr.data}
								bind:currentLanguage={mgr.currentLanguage}
								bind:currentCode={mgr.currentCode}
								bind:editor={mgr.editor}
								compiling={mgr.compiling}
								authLoggedIn={$authLoggedIn}
								lessonCompleted={mgr.lessonCompleted}
								showSolution={mgr.showSolution}
								slug={mgr.slug}
								onRun={mgr.handleRun.bind(mgr)}
								onReset={mgr.handleReset.bind(mgr)}
								onShowSolution={mgr.handleShowSolution.bind(mgr)}
							/>
						</div>
					{/if}

						{#if mgr.data?.active_tabs?.includes('quiz')}
							<div class="tab-panel quiz-panel" class:tab-hidden={mgr.activeTab !== 'quiz'}>
								<QuizTab mgr={mgr} />
							</div>
						{/if}

					<div class="tab-panel" class:tab-hidden={mgr.activeTab !== 'output'}>
						<OutputPanel sections={mgr.outputSections}>
							{#snippet actions()}
								<button class="btn btn-success btn-sm btn-run-all" onclick={() => mgr.handleRunAll()} disabled={mgr.compiling}>
									{mgr.compiling ? 'Mengevaluasi...' : '▶ Run Keseluruhan'}
								</button>
							{/snippet}
						</OutputPanel>
					</div>
				</div>

				<CelebrationOverlay bind:visible={mgr.showCelebration} />
			</div>
		</div>
	{/key}
{/if}
