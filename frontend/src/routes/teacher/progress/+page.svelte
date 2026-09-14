<script lang="ts">
	import { authIsTeacher, authToken } from '$stores/auth';

	interface LessonHeader {
		filename: string;
		title: string;
		sub_bab?: string;
		sub_bab_title?: string;
	}

	interface StudentProgress {
		id: string;
		nama_siswa: string;
		role: 'teacher' | 'student';
		completed_count: number;
		[key: string]: string | number | boolean;
	}

	interface SubBabMeta {
		folder: string;
		title: string;
	}

	interface StudentLessonDetail {
		id: string;
		nama_siswa: string;
		role: 'teacher' | 'student';
		status: string;
		composite: number | null;
		exercise_passed: boolean;
		quiz_score: string;
		has_violation: boolean;
		violation_reason: string;
		violation_time: string;
		eval_score: string;
		diag_score: string;
		diag_unmastered: string[];
	}

	interface LessonNode {
		lesson: LessonHeader;
		key: string;
		completedStudents: StudentLessonDetail[];
	}

	interface SubBabGroup {
		folder: string;
		title: string;
		lessons: LessonNode[];
		totalLessons: number;
		totalCompletions: number;
	}

	// Parse `_diag_unmastered` JSON string
	function parseUnmastered(raw: string | number | boolean | undefined): string[] {
		if (typeof raw !== 'string') return [];
		try {
			const parsed = JSON.parse(raw);
			return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : [];
		} catch {
			return [];
		}
	}

	let students = $state<StudentProgress[]>([]);
	let lessons = $state<LessonHeader[]>([]);
	let subBabList = $state<SubBabMeta[]>([]);
	let loading = $state(true);
	let searchQuery = $state('');

	// Track open/collapsed state for tree nodes
	let openSubBabs = $state<Record<string, boolean>>({});
	let openLessons = $state<Record<string, boolean>>({});

	// Reactively load data when auth is ready
	$effect(() => {
		if ($authIsTeacher && $authToken) {
			loadData();
		} else if (!$authIsTeacher) {
			loading = false;
		}
	});

	async function loadData() {
		if (!$authIsTeacher || !$authToken) return;

		loading = true;
		try {
			const res = await fetch(`/api/progress-report.json?token=${encodeURIComponent($authToken)}&_t=${Date.now()}`, {
				cache: 'no-store'
			});
			const data = await res.json();
			students = data.students ?? [];
			lessons = data.lessons ?? [];
			subBabList = data.sub_bab_list ?? [];

			// Secara default, buka semua sub-bab pada pemuatan awal
			const initialSubBabs: Record<string, boolean> = {};
			for (const l of lessons) {
				const folderKey = l.sub_bab || '_uncategorized';
				initialSubBabs[folderKey] = true;
			}
			openSubBabs = initialSubBabs;
		} catch {
			// API not available
		} finally {
			loading = false;
		}
	}

	async function handleReset(studentId: string, lessonName: string, studentName: string) {
		if (!window.confirm(`Apakah Anda yakin ingin me-reset progres materi "${lessonName}" untuk siswa "${studentName}"?`)) {
			return;
		}

		try {
			const res = await fetch('/api/reset-progress', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					teacher_token: $authToken,
					student_id: studentId,
					lesson_name: lessonName
				})
			});
			const data = await res.json();
			if (data.success) {
				await loadData();
			} else {
				alert('Gagal me-reset: ' + data.message);
			}
		} catch {
			alert('Terjadi kesalahan saat menghubungi server.');
		}
	}

	function toggleSubBab(folder: string) {
		openSubBabs[folder] = !openSubBabs[folder];
	}

	function toggleLesson(lessonKey: string) {
		openLessons[lessonKey] = !openLessons[lessonKey];
	}

	function expandAll() {
		const newSubBabs: Record<string, boolean> = {};
		const newLessons: Record<string, boolean> = {};
		for (const group of treeGroups) {
			newSubBabs[group.folder] = true;
			for (const lNode of group.lessons) {
				newLessons[lNode.key] = true;
			}
		}
		openSubBabs = newSubBabs;
		openLessons = newLessons;
	}

	function collapseAll() {
		openSubBabs = {};
		openLessons = {};
	}

	function isCompleted(s: StudentProgress, key: string): boolean {
		const status = s[key];
		const composite = s[key + '_composite'];
		const exercisePassed = s[key + '_exercise_passed'];
		if (composite !== null && composite !== undefined) return true;
		if (exercisePassed === true) return true;
		if (status === 'completed' || status === 'done') return true;
		if (typeof status === 'string' && status !== 'not_started' && status !== '') return true;
		return false;
	}

	// Membangun struktur tree hierarkis: Sub-Bab -> Materi -> Siswa Selesai
	const treeGroups = $derived.by(() => {
		const query = searchQuery.trim().toLowerCase();
		const groupsMap = new Map<string, { title: string; lessons: LessonHeader[] }>();
		const uncategorizedLessons: LessonHeader[] = [];

		// Daftarkan sub-bab yang diketahui dari backend
		for (const sb of subBabList) {
			groupsMap.set(sb.folder, { title: sb.title, lessons: [] });
		}

		for (const lesson of lessons) {
			if (lesson.sub_bab) {
				if (!groupsMap.has(lesson.sub_bab)) {
					groupsMap.set(lesson.sub_bab, {
						title: lesson.sub_bab_title || lesson.sub_bab,
						lessons: []
					});
				}
				groupsMap.get(lesson.sub_bab)!.lessons.push(lesson);
			} else {
				uncategorizedLessons.push(lesson);
			}
		}

		const result: SubBabGroup[] = [];

		for (const [folder, group] of groupsMap) {
			if (group.lessons.length === 0) continue;

			const lessonNodes: LessonNode[] = [];
			let totalCompletions = 0;

			for (const lesson of group.lessons) {
				const key = lesson.filename.replace('.md', '');
				const completedStudents: StudentLessonDetail[] = [];

				for (const s of students) {
					if (isCompleted(s, key)) {
						completedStudents.push({
							id: s.id,
							nama_siswa: s.nama_siswa,
							role: s.role,
							status: String(s[key] ?? ''),
							composite: typeof s[key + '_composite'] === 'number' ? (s[key + '_composite'] as number) : null,
							exercise_passed: Boolean(s[key + '_exercise_passed']),
							quiz_score: String(s[key + '_quiz_score'] ?? ''),
							has_violation: Boolean(s[key + '_has_violation']),
							violation_reason: String(s[key + '_termination_reason'] ?? ''),
							violation_time: String(s[key + '_attempt_finished_at'] ?? ''),
							eval_score: String(s[key + '_eval'] ?? ''),
							diag_score: String(s[key + '_diag'] ?? ''),
							diag_unmastered: parseUnmastered(s[key + '_diag_unmastered'])
						});
					}
				}

				totalCompletions += completedStudents.length;

				// Filter pencarian jika ada
				const matchesQuery = !query ||
					lesson.title.toLowerCase().includes(query) ||
					lesson.filename.toLowerCase().includes(query) ||
					group.title.toLowerCase().includes(query) ||
					folder.toLowerCase().includes(query) ||
					completedStudents.some(s => s.nama_siswa.toLowerCase().includes(query));

				if (matchesQuery) {
					lessonNodes.push({
						lesson,
						key,
						completedStudents
					});
				}
			}

			if (lessonNodes.length > 0) {
				result.push({
					folder,
					title: group.title,
					lessons: lessonNodes,
					totalLessons: group.lessons.length,
					totalCompletions
				});
			}
		}

		// Kelompok materi tanpa sub-bab
		if (uncategorizedLessons.length > 0) {
			const lessonNodes: LessonNode[] = [];
			let totalCompletions = 0;

			for (const lesson of uncategorizedLessons) {
				const key = lesson.filename.replace('.md', '');
				const completedStudents: StudentLessonDetail[] = [];

				for (const s of students) {
					if (isCompleted(s, key)) {
						completedStudents.push({
							id: s.id,
							nama_siswa: s.nama_siswa,
							role: s.role,
							status: String(s[key] ?? ''),
							composite: typeof s[key + '_composite'] === 'number' ? (s[key + '_composite'] as number) : null,
							exercise_passed: Boolean(s[key + '_exercise_passed']),
							quiz_score: String(s[key + '_quiz_score'] ?? ''),
							has_violation: Boolean(s[key + '_has_violation']),
							violation_reason: String(s[key + '_termination_reason'] ?? ''),
							violation_time: String(s[key + '_attempt_finished_at'] ?? ''),
							eval_score: String(s[key + '_eval'] ?? ''),
							diag_score: String(s[key + '_diag'] ?? ''),
							diag_unmastered: parseUnmastered(s[key + '_diag_unmastered'])
						});
					}
				}

				totalCompletions += completedStudents.length;

				const matchesQuery = !query ||
					lesson.title.toLowerCase().includes(query) ||
					lesson.filename.toLowerCase().includes(query) ||
					completedStudents.some(s => s.nama_siswa.toLowerCase().includes(query));

				if (matchesQuery) {
					lessonNodes.push({
						lesson,
						key,
						completedStudents
					});
				}
			}

			if (lessonNodes.length > 0) {
				result.push({
					folder: '_uncategorized',
					title: 'Lainnya (Materi Umum)',
					lessons: lessonNodes,
					totalLessons: uncategorizedLessons.length,
					totalCompletions
				});
			}
		}

		return result;
	});

	const studentRows = $derived(students.filter((s) => s.role === 'student'));
	const totalLessonsCount = $derived(lessons.length);
</script>

<svelte:head>
	<title>Perkembangan Siswa - Elemes LMS</title>
</svelte:head>

<div class="header-section">
	<div>
		<h1>Laporan Perkembangan Siswa</h1>
		<p class="subtitle">Pantau kemajuan belajar siswa per sub-bab dan materi secara terstruktur.</p>
	</div>
	<div class="header-actions">
		<a href="/teacher/classroom" class="btn btn-sm btn-outline">
			&larr; Manajemen Kelas
		</a>
		<a
			href="/api/progress-report/export-csv?token={encodeURIComponent($authToken)}"
			class="btn btn-sm btn-secondary"
			title="Unduh laporan progres semua siswa dalam bentuk berkas CSV"
		>
			&#8595; Export Laporan CSV
		</a>
	</div>
</div>

{#if loading}
	<p class="loading">Memuat data progres...</p>
{:else if !$authIsTeacher}
	<p class="empty">Anda tidak memiliki akses ke halaman ini.</p>
{:else}
	<div class="toolbar">
		<div class="stats-group">
			<span class="stat-pill"><strong>{treeGroups.length}</strong> Sub-Bab</span>
			<span class="stat-pill"><strong>{totalLessonsCount}</strong> Materi</span>
			<span class="stat-pill"><strong>{studentRows.length}</strong> Siswa</span>
		</div>

		<div class="search-box">
			<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>
			</svg>
			<input
				type="text"
				placeholder="Cari sub-bab, materi, atau siswa..."
				bind:value={searchQuery}
			/>
			{#if searchQuery}
				<button class="clear-search" onclick={() => (searchQuery = '')} aria-label="Hapus pencarian">&times;</button>
			{/if}
		</div>

		<div class="tree-controls">
			<button class="btn-text" onclick={expandAll} title="Buka semua folder dan materi">
				Buka Semua
			</button>
			<span class="divider">|</span>
			<button class="btn-text" onclick={collapseAll} title="Tutup semua folder dan materi">
				Tutup Semua
			</button>
		</div>
	</div>

	{#if treeGroups.length === 0}
		<div class="empty-box">
			{#if searchQuery}
				<p class="empty-title">Tidak ada hasil yang cocok</p>
				<p class="empty-desc">Tidak ditemukan sub-bab, materi, atau siswa dengan kata kunci "<strong>{searchQuery}</strong>".</p>
				<button class="btn btn-sm btn-secondary" onclick={() => (searchQuery = '')}>Hapus Pencarian</button>
			{:else}
				<p class="empty-title">Belum ada materi pelajaran</p>
				<p class="empty-desc">Materi pelajaran belum terdeteksi di dalam direktori konten.</p>
			{/if}
		</div>
	{:else}
		<div class="tree-container">
			{#each treeGroups as group (group.folder)}
				{@const isSubBabOpen = openSubBabs[group.folder] ?? true}
				<div class="sub-bab-card" class:is-open={isSubBabOpen}>
					<!-- Level 1: Sub-Bab Folder -->
					<button
						type="button"
						class="sub-bab-header"
						onclick={() => toggleSubBab(group.folder)}
						aria-expanded={isSubBabOpen}
					>
						<span class="chevron" class:expanded={isSubBabOpen}>▶</span>
						<span class="folder-icon">
							{#if isSubBabOpen}📂{:else}📁{/if}
						</span>
						<span class="sub-bab-title">{group.title}</span>
						{#if group.folder !== '_uncategorized'}
							<span class="folder-slug">bab/{group.folder}</span>
						{/if}

						<div class="sub-bab-meta">
							<span class="badge badge-subtle">{group.lessons.length} materi</span>
							<span class="badge badge-accent">{group.totalCompletions} penyelesaian</span>
						</div>
					</button>

					<!-- Level 2: Daftar Materi di dalam Sub-Bab -->
					{#if isSubBabOpen}
						<div class="lessons-container">
							{#each group.lessons as item (item.key)}
								{@const isLessonOpen = openLessons[item.key] ?? (searchQuery !== '' && item.completedStudents.length > 0)}
								{@const studentCount = item.completedStudents.length}
								<div class="lesson-item" class:is-lesson-open={isLessonOpen}>
									<button
										type="button"
										class="lesson-header"
										onclick={() => toggleLesson(item.key)}
										aria-expanded={isLessonOpen}
									>
										<span class="tree-branch-line"></span>
										<span class="chevron lesson-chevron" class:expanded={isLessonOpen}>▶</span>
										<span class="file-icon">📄</span>
										<span class="lesson-title">{item.lesson.title}</span>
										<span class="lesson-filename">{item.lesson.filename}</span>

										<div class="lesson-meta">
											{#if studentCount > 0}
												<span class="badge badge-success">
													<strong>{studentCount}</strong> siswa selesai
												</span>
											{:else}
												<span class="badge badge-muted">0 siswa selesai</span>
											{/if}
										</div>
									</button>

									<!-- Level 3: Siswa yang Pernah Menyelesaikan Materi -->
									{#if isLessonOpen}
										<div class="students-container">
											{#if studentCount === 0}
												<div class="student-empty-row">
													<span class="tree-subbranch-line"></span>
													<span class="empty-student-text">Belum ada siswa yang menyelesaikan materi ini.</span>
												</div>
											{:else}
												{#each item.completedStudents as student (student.id)}
													{@const isTeacher = student.role === 'teacher'}
													<div class="student-row">
														<span class="tree-subbranch-line"></span>
														<div class="student-main">
															<span class="user-icon">👤</span>
															<span class="student-name">
																{student.nama_siswa}
																{#if isTeacher}
																	<span class="badge teacher-badge">Guru</span>
																{/if}
															</span>

															<div class="student-badges">
																{#if student.composite !== null}
																	<span class="badge badge-score" title="Skor Komposit (0-100)">
																		Skor: {student.composite}%
																	</span>
																{/if}

																{#if student.exercise_passed || student.status === 'completed'}
																	<span class="badge badge-passed" title="Latihan Selesai">&#10003; Latihan</span>
																{/if}

																{#if student.quiz_score}
																	<span class="badge badge-quiz" title="Skor Kuis">Kuis: {student.quiz_score}</span>
																{/if}

																{#if student.has_violation}
																	<span
																		class="badge badge-violation"
																		title="Pelanggaran Anti-cheat: {student.violation_reason}{student.violation_time ? ' pada ' + student.violation_time : ''}"
																	>
																		&#9888; Pelanggaran
																	</span>
																{/if}

																{#if student.eval_score}
																	<span class="badge badge-detail" title="Skor Soal Evaluasi">Eval: {student.eval_score}</span>
																{/if}

																{#if student.diag_score}
																	<span class="badge badge-detail" title="Skor Soal Diagnostik">Diag: {student.diag_score}</span>
																	{#if student.diag_unmastered.length > 0}
																		<span class="badge badge-unmastered" title="Belum dikuasai: {student.diag_unmastered.join(', ')}">
																			{student.diag_unmastered.length} belum dikuasai
																		</span>
																	{/if}
																{/if}
															</div>

															<button
																class="btn-reset"
																onclick={() => handleReset(student.id, item.key, student.nama_siswa)}
																title="Reset progres materi ini untuk siswa {student.nama_siswa}"
															>
																↻ Reset
															</button>
														</div>
													</div>
												{/each}
											{/if}
										</div>
									{/if}
								</div>
							{/each}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
{/if}

<style>
	.header-section {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		flex-wrap: wrap;
		gap: 1rem;
		margin-bottom: 1.25rem;
	}
	h1 {
		font-size: 1.5rem;
		margin: 0 0 0.25rem 0;
	}
	.subtitle {
		color: var(--color-text-muted);
		font-size: 0.9rem;
		margin: 0;
	}
	.header-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.loading, .empty {
		text-align: center;
		padding: 3rem;
		color: var(--color-text-muted);
	}

	.toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 1rem;
		margin-bottom: 1.25rem;
		padding: 0.75rem 1rem;
		background: var(--color-bg-secondary);
		border-radius: var(--radius);
		border: 1px solid var(--color-border);
	}
	.stats-group {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.stat-pill {
		font-size: 0.85rem;
		padding: 0.2rem 0.55rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		color: var(--color-text);
	}

	.search-box {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.3rem 0.65rem;
		min-width: 260px;
		flex: 1;
		max-width: 380px;
		color: var(--color-text-muted);
	}
	.search-box input {
		border: none;
		background: transparent;
		color: var(--color-text);
		font-size: 0.85rem;
		width: 100%;
		outline: none;
	}
	.clear-search {
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		font-size: 1.1rem;
		line-height: 1;
		padding: 0;
	}
	.clear-search:hover {
		color: var(--color-text);
	}

	.tree-controls {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
	}
	.btn-text {
		background: none;
		border: none;
		color: var(--color-primary);
		cursor: pointer;
		padding: 0;
		font-size: 0.85rem;
	}
	.btn-text:hover {
		text-decoration: underline;
	}
	.divider {
		color: var(--color-border);
	}

	.btn {
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		font-weight: 500;
		border-radius: var(--radius);
		cursor: pointer;
		text-decoration: none;
		transition: all 0.15s;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.btn-sm {
		padding: 0.35rem 0.75rem;
		font-size: 0.8rem;
	}
	.btn-outline {
		background: transparent;
		border: 1px solid var(--color-primary);
		color: var(--color-primary);
	}
	.btn-outline:hover {
		background: var(--color-primary);
		color: #fff;
	}
	.btn-secondary {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		color: var(--color-text);
	}
	.btn-secondary:hover {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}

	.empty-box {
		text-align: center;
		padding: 3rem 1.5rem;
		background: var(--color-bg-secondary);
		border: 1px dashed var(--color-border);
		border-radius: var(--radius);
		margin: 1.5rem 0;
	}
	.empty-title {
		font-size: 1.1rem;
		font-weight: 600;
		margin: 0 0 0.5rem 0;
	}
	.empty-desc {
		color: var(--color-text-muted);
		max-width: 450px;
		margin: 0 auto 1.5rem auto;
		font-size: 0.9rem;
	}

	/* Tree View Styles */
	.tree-container {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.sub-bab-card {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-bg);
		overflow: hidden;
		transition: border-color 0.15s;
	}
	.sub-bab-card.is-open {
		border-color: color-mix(in srgb, var(--color-primary) 35%, var(--color-border));
	}

	/* Level 1: Sub-Bab Header */
	.sub-bab-header {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.75rem 1rem;
		background: var(--color-bg-secondary);
		border: none;
		border-bottom: 1px solid transparent;
		cursor: pointer;
		text-align: left;
		color: var(--color-text);
		font-size: 0.95rem;
		transition: background-color 0.15s;
	}
	.sub-bab-card.is-open .sub-bab-header {
		border-bottom-color: var(--color-border);
	}
	.sub-bab-header:hover {
		background: color-mix(in srgb, var(--color-primary) 6%, var(--color-bg-secondary));
	}
	.chevron {
		font-size: 0.65rem;
		color: var(--color-text-muted);
		transition: transform 0.15s ease;
		display: inline-block;
		width: 12px;
		text-align: center;
	}
	.chevron.expanded {
		transform: rotate(90deg);
	}
	.folder-icon {
		font-size: 1.15rem;
		line-height: 1;
	}
	.sub-bab-title {
		font-weight: 600;
		font-size: 1rem;
	}
	.folder-slug {
		font-family: monospace;
		font-size: 0.75rem;
		color: var(--color-text-muted);
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		padding: 0.1rem 0.35rem;
		border-radius: 4px;
	}
	.sub-bab-meta {
		margin-left: auto;
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	/* Level 2: Lessons Container */
	.lessons-container {
		padding: 0.4rem 0.5rem 0.4rem 1.25rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		position: relative;
	}
	.lessons-container::before {
		content: '';
		position: absolute;
		top: 0.5rem;
		bottom: 0.5rem;
		left: 1.8rem;
		width: 1px;
		background: var(--color-border);
	}

	.lesson-item {
		border-radius: var(--radius);
		overflow: hidden;
		transition: background-color 0.15s;
	}

	.lesson-header {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem 0.5rem 1.5rem;
		background: transparent;
		border: 1px solid transparent;
		border-radius: var(--radius);
		cursor: pointer;
		text-align: left;
		color: var(--color-text);
		font-size: 0.9rem;
		position: relative;
		transition: all 0.15s;
	}
	.lesson-header:hover {
		background: var(--color-bg-secondary);
		border-color: var(--color-border);
	}
	.is-lesson-open .lesson-header {
		background: var(--color-bg-secondary);
		border-color: var(--color-border);
	}
	.tree-branch-line {
		position: absolute;
		left: 0.55rem;
		top: 50%;
		width: 0.6rem;
		height: 1px;
		background: var(--color-border);
	}
	.lesson-chevron {
		font-size: 0.6rem;
	}
	.file-icon {
		font-size: 1rem;
		line-height: 1;
	}
	.lesson-title {
		font-weight: 500;
	}
	.lesson-filename {
		font-family: monospace;
		font-size: 0.72rem;
		color: var(--color-text-muted);
	}
	.lesson-meta {
		margin-left: auto;
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	/* Level 3: Students Container */
	.students-container {
		padding: 0.3rem 0.5rem 0.4rem 3rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		position: relative;
	}
	.students-container::before {
		content: '';
		position: absolute;
		top: 0.2rem;
		bottom: 0.5rem;
		left: 3.2rem;
		width: 1px;
		background: var(--color-border);
	}

	.student-row {
		display: flex;
		align-items: center;
		position: relative;
	}
	.tree-subbranch-line {
		position: absolute;
		left: 0.2rem;
		top: 50%;
		width: 0.7rem;
		height: 1px;
		background: var(--color-border);
	}
	.student-empty-row {
		display: flex;
		align-items: center;
		position: relative;
		padding: 0.4rem 0.5rem 0.4rem 1.25rem;
	}
	.empty-student-text {
		color: var(--color-text-muted);
		font-style: italic;
		font-size: 0.8rem;
	}

	.student-main {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.6rem;
		width: 100%;
		margin-left: 1.25rem;
		padding: 0.4rem 0.75rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		font-size: 0.85rem;
		transition: border-color 0.15s;
	}
	.student-main:hover {
		border-color: color-mix(in srgb, var(--color-primary) 50%, var(--color-border));
	}
	.user-icon {
		font-size: 0.85rem;
		line-height: 1;
		color: var(--color-text-muted);
	}
	.student-name {
		font-weight: 500;
		min-width: 130px;
	}
	.student-badges {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	/* Badges */
	.badge {
		display: inline-flex;
		align-items: center;
		border-radius: 999px;
		padding: 0.12rem 0.5rem;
		font-size: 0.7rem;
		font-weight: 600;
		white-space: nowrap;
	}
	.badge-subtle {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		color: var(--color-text-muted);
	}
	.badge-accent {
		background: color-mix(in srgb, var(--color-primary) 12%, var(--color-bg));
		border: 1px solid color-mix(in srgb, var(--color-primary) 30%, var(--color-bg));
		color: var(--color-primary);
	}
	.badge-success {
		background: #e8f5e9;
		color: #2e7d32;
		border: 1px solid #c8e6c9;
	}
	.badge-muted {
		background: var(--color-bg-secondary);
		border: 1px solid var(--color-border);
		color: var(--color-text-muted);
		opacity: 0.75;
	}
	.badge-score {
		background: color-mix(in srgb, var(--color-primary) 10%, var(--color-bg));
		border: 1px solid color-mix(in srgb, var(--color-primary) 35%, var(--color-bg));
		color: var(--color-primary);
		font-weight: 700;
	}
	.badge-passed {
		background: #e8f5e9;
		color: #2e7d32;
		border: 1px solid #c8e6c9;
	}
	.badge-quiz {
		background: #e3f2fd;
		color: #1565c0;
		border: 1px solid #bbdefb;
	}
	.badge-violation {
		background: #fff3e0;
		color: #e65100;
		border: 1px solid #ffe0b2;
	}
	.badge-detail {
		background: var(--color-bg-secondary);
		border: 1px solid var(--color-border);
		color: var(--color-text-muted);
	}
	.badge-unmastered {
		background: #ffebee;
		color: #c62828;
		border: 1px solid #ffcdd2;
	}
	.teacher-badge {
		background: color-mix(in srgb, var(--color-primary) 10%, var(--color-bg));
		border: 1px solid color-mix(in srgb, var(--color-primary) 40%, var(--color-bg));
		color: var(--color-primary);
		font-size: 0.65rem;
		margin-left: 0.25rem;
	}

	.btn-reset {
		margin-left: auto;
		background: transparent;
		border: 1px solid var(--color-border);
		border-radius: 4px;
		color: var(--color-text-muted);
		cursor: pointer;
		font-size: 0.72rem;
		padding: 0.15rem 0.45rem;
		transition: all 0.15s;
	}
	.btn-reset:hover {
		border-color: #fa5252;
		color: #fa5252;
		background: #fff5f5;
	}
</style>
