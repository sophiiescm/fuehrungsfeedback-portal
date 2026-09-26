<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import {
		surveysApi,
		type SurveyVersionDetail,
		type Question,
		type QuestionType
	} from '$lib/api/surveys';
	import { ApiError } from '$lib/api/client';

	const versionId = $derived(Number(page.params.versionId));

	let detail = $state<SurveyVersionDetail | null>(null);
	let error = $state('');
	let showPreview = $state(false);
	let newDimensionName = $state('');
	let draggedQuestionId = $state<number | null>(null);
	let transferring = $state(false);
	let transferMessage = $state('');

	const TYPE_LABELS: Record<QuestionType, string> = {
		likert: 'Likert-Skala',
		nps: 'NPS (0–10)',
		choice: 'Auswahlfrage',
		freitext: 'Freitext'
	};
	const OPERATORS: Record<string, string> = {
		eq: '=',
		neq: '≠',
		lt: '<',
		lte: '≤',
		gt: '>',
		gte: '≥'
	};

	// Formular "Frage hinzufuegen" (pro Sektion: Dimension-ID oder null)
	let addFormOpenFor = $state<number | null | undefined>(undefined);
	const PRESETS: Record<number, string[]> = {
		4: ['Trifft gar nicht zu', 'Trifft eher nicht zu', 'Trifft eher zu', 'Trifft voll zu'],
		5: ['Trifft gar nicht zu', 'Trifft eher nicht zu', 'Teils/teils', 'Trifft eher zu', 'Trifft voll zu'],
		6: ['Trifft gar nicht zu', 'Trifft nicht zu', 'Trifft eher nicht zu', 'Trifft eher zu', 'Trifft zu', 'Trifft voll zu'],
		7: ['Trifft gar nicht zu', 'Trifft nicht zu', 'Trifft eher nicht zu', 'Teils/teils', 'Trifft eher zu', 'Trifft zu', 'Trifft voll zu']
	};
	function setScale(n: number) {
		form.scaleMax = n;
		form.labels = [...PRESETS[n]];
	}
	let form = $state({
		type: 'likert' as QuestionType,
		text: '',
		help: '',
		scaleMax: 5,
		labels: [...PRESETS[5]],
		poleMin: 'Sehr unwahrscheinlich',
		poleMax: 'Sehr wahrscheinlich',
		mandatory: true,
		options: ['', '', ''],
		allowMultiple: false,
		branching: false,
		showIfQuestion: null as number | null,
		showIfOp: 'lt',
		showIfValue: ''
	});

	async function load() {
		error = '';
		try {
			detail = await surveysApi.getVersion(versionId);
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Konnte Version nicht laden';
		}
	}
	onMount(load);
	$effect(() => {
		if (versionId) load();
	});

	const isLocked = $derived(detail?.status === 'gesperrt');
	const editable = $derived(!isLocked && !showPreview);
	const orderedQuestions = $derived(
		detail ? [...detail.questions].sort((a, b) => a.sort_order - b.sort_order) : []
	);
	// Bezugsfragen fuer Verzweigungen: nur Skala/NPS/Einfachauswahl
	const branchSources = $derived(
		orderedQuestions.filter(
			(q) => q.type === 'likert' || q.type === 'nps' || (q.type === 'choice' && !q.allow_multiple)
		)
	);
	const sourceQuestion = $derived(branchSources.find((q) => q.id === form.showIfQuestion));

	function questionsFor(dimensionId: number | null): Question[] {
		return orderedQuestions.filter((q) => q.dimension_id === dimensionId);
	}
	const nameOf = (id: number | null) => orderedQuestions.find((q) => q.id === id)?.text ?? '?';

	async function addDimension() {
		if (!newDimensionName.trim() || !detail) return;
		await surveysApi.addDimension(detail.id, newDimensionName.trim());
		newDimensionName = '';
		await load();
	}
	async function deleteDimension(id: number) {
		await surveysApi.deleteDimension(id);
		await load();
	}

	function openAddForm(dimensionId: number | null) {
		addFormOpenFor = dimensionId;
		form = {
			type: dimensionId === null ? 'freitext' : 'likert',
			text: '',
			help: '',
			scaleMax: 5,
			labels: [...PRESETS[5]],
			poleMin: 'Sehr unwahrscheinlich',
			poleMax: 'Sehr wahrscheinlich',
			mandatory: true,
			options: ['', '', ''],
			allowMultiple: false,
			branching: false,
			showIfQuestion: null,
			showIfOp: 'lt',
			showIfValue: ''
		};
	}

	async function submitAddForm() {
		if (!detail || !form.text.trim() || addFormOpenFor === undefined) return;
		error = '';
		const options = form.type === 'choice' ? form.options.map((o) => o.trim()).filter(Boolean) : null;
		const isLikert = form.type === 'likert';
		try {
			await surveysApi.addQuestion(detail.id, {
				type: form.type,
				text: form.text.trim(),
				dimension_id: addFormOpenFor,
				scale_min: 1,
				scale_max: form.scaleMax,
				pole_label_min: isLikert ? form.labels[0] : form.poleMin,
				pole_label_max: isLikert ? form.labels[form.labels.length - 1] : form.poleMax,
				scale_labels: isLikert ? form.labels.map((l) => l.trim()) : undefined,
				mandatory: form.mandatory,
				help_text: form.help.trim() || null,
				options,
				allow_multiple: form.type === 'choice' && form.allowMultiple,
				show_if_question_id: form.branching ? form.showIfQuestion : null,
				show_if_operator: form.branching ? form.showIfOp : null,
				show_if_value: form.branching ? form.showIfValue : null
			});
			addFormOpenFor = undefined;
			await load();
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Frage konnte nicht angelegt werden';
		}
	}

	async function deleteQuestion(id: number) {
		await surveysApi.deleteQuestion(id);
		await load();
	}
	async function toggleMandatory(q: Question) {
		await surveysApi.updateQuestion(q.id, { mandatory: !q.mandatory });
		await load();
	}
	async function toggleMultiple(q: Question) {
		await surveysApi.updateQuestion(q.id, { allow_multiple: !q.allow_multiple });
		await load();
	}

	function onDragStart(questionId: number) {
		draggedQuestionId = questionId;
	}
	async function onDrop(targetDimensionId: number | null, targetIndex: number) {
		if (!detail || draggedQuestionId === null) return;
		const dragged = detail.questions.find((q) => q.id === draggedQuestionId);
		if (!dragged) return;
		const targetQuestions = questionsFor(targetDimensionId).filter((q) => q.id !== draggedQuestionId);
		targetQuestions.splice(targetIndex, 0, { ...dragged, dimension_id: targetDimensionId });
		const sections = [...detail.dimensions.map((d) => d.id), null];
		let order = 1;
		const payload: { id: number; dimension_id: number | null; sort_order: number }[] = [];
		for (const sectionId of sections) {
			const qs = sectionId === targetDimensionId ? targetQuestions : questionsFor(sectionId);
			for (const q of qs) payload.push({ id: q.id, dimension_id: sectionId, sort_order: order++ });
		}
		draggedQuestionId = null;
		detail = await surveysApi.reorder(detail.id, payload);
	}

	async function cloneVersion() {
		if (!detail) return;
		const clone = await surveysApi.clone(detail.id);
		await goto(`/survey-builder/${clone.id}`);
	}
	async function transfer() {
		if (!detail) return;
		transferring = true;
		transferMessage = '';
		try {
			const result = await surveysApi.transfer(detail.id);
			transferMessage = `Veröffentlicht – bereit für Befragungsrunden.`;
			await load();
		} catch (e) {
			transferMessage = e instanceof ApiError ? e.message : 'Übertragung fehlgeschlagen';
		} finally {
			transferring = false;
		}
	}
	const scalePoints = (q: Question) => {
		if (q.type === 'nps') return Array.from({ length: 11 }, (_, i) => i);
		const min = q.scale_min ?? 1;
		return Array.from({ length: (q.scale_max ?? 5) - min + 1 }, (_, i) => min + i);
	};
</script>

{#snippet questionRow(q: Question, dimId: number | null, idx: number)}
	<div
		role="listitem"
		draggable={editable}
		ondragstart={() => onDragStart(q.id)}
		ondragover={(e) => e.preventDefault()}
		ondrop={(e) => {
			e.stopPropagation();
			onDrop(dimId, idx);
		}}
		class="glass-surface flex items-start gap-3 p-3"
	>
		{#if editable}<span style="color: var(--text-muted)" class="cursor-grab pt-1">⠿</span>{/if}
		<div class="flex-1">
			<p class="text-sm" style="color: var(--text-primary)">
				{q.text}{#if q.mandatory}<span style="color: var(--danger)"> *</span>{/if}
			</p>
			{#if q.help_text}<p class="text-xs italic" style="color: var(--text-muted)">{q.help_text}</p>{/if}

			{#if showPreview}
				{#if q.type === 'likert' || q.type === 'nps'}
					<div class="mt-2 flex flex-wrap gap-3">
						{#each scalePoints(q) as point, i}
							<label class="flex max-w-[6.5rem] flex-col items-center text-center text-xs" style="color: var(--text-muted)">
								<input type="radio" disabled />
								{q.scale_labels?.[i] ?? (point === scalePoints(q)[0] ? (q.pole_label_min ?? point) : point === scalePoints(q).at(-1) ? (q.pole_label_max ?? point) : point)}
							</label>
						{/each}
					</div>
				{:else if q.type === 'choice'}
					<div class="mt-2 flex flex-col gap-1 text-xs" style="color: var(--text-secondary)">
						{#each q.options ?? [] as o}
							<label><input type={q.allow_multiple ? 'checkbox' : 'radio'} disabled /> {o}</label>
						{/each}
						<span style="color: var(--text-muted)">{q.allow_multiple ? 'Mehrfachantworten möglich' : 'Eine Antwort'}</span>
					</div>
				{:else}
					<textarea disabled class="glass-surface mt-2 w-full rounded p-2 text-xs"></textarea>
				{/if}
				{#if q.show_if_question_id}
					<p class="mt-1 text-[11px]" style="color: var(--accent)">
						Wird nur angezeigt, wenn „{nameOf(q.show_if_question_id)}“ {OPERATORS[q.show_if_operator ?? 'eq']} {q.show_if_value}
					</p>
				{/if}
			{:else}
				<p class="mt-1 text-xs" style="color: var(--text-muted)">
					<span class="rounded-full px-2 py-0.5" style="background: var(--surface-glass-strong)">{TYPE_LABELS[q.type]}</span>
					{#if q.type === 'likert'}{q.scale_labels ? q.scale_labels.map((l, i) => `${i + 1} = ${l}`).join(' · ') : `Skala ${q.scale_min}–${q.scale_max}: „${q.pole_label_min}“ … „${q.pole_label_max}“`}{/if}
					{#if q.type === 'choice'}{q.allow_multiple ? 'Mehrfachauswahl' : 'Einfachauswahl'}: {(q.options ?? []).join(' · ')}{/if}
				</p>
				{#if q.show_if_question_id}
					<p class="text-[11px]" style="color: var(--accent)">
						↳ nur wenn „{nameOf(q.show_if_question_id)}“ {OPERATORS[q.show_if_operator ?? 'eq']} {q.show_if_value}
					</p>
				{/if}
			{/if}
		</div>
		{#if editable}
			{#if q.type === 'choice'}
				<button onclick={() => toggleMultiple(q)} class="text-xs" style="color: var(--text-secondary)">
					{q.allow_multiple ? 'Mehrfach ✓' : 'Mehrfach ✗'}
				</button>
			{/if}
			<button onclick={() => toggleMandatory(q)} class="text-xs" style="color: var(--text-secondary)">{q.mandatory ? 'Pflicht' : 'Optional'}</button>
			<button onclick={() => deleteQuestion(q.id)} class="text-xs" style="color: var(--danger)">Löschen</button>
		{/if}
	</div>
{/snippet}

{#snippet addForm()}
	<div class="glass-surface mt-3 flex flex-col gap-2 p-3">
		<div class="flex flex-wrap gap-2">
			{#each Object.entries(TYPE_LABELS) as [t, label] (t)}
				<button
					onclick={() => (form.type = t as QuestionType)}
					class="rounded-full px-3 py-1 text-xs"
					style="background: {form.type === t ? 'var(--accent)' : 'var(--surface-glass-strong)'}; color: {form.type === t ? 'var(--accent-contrast)' : 'var(--text-primary)'}"
				>{label}</button>
			{/each}
		</div>
		<textarea placeholder="Fragetext" bind:value={form.text} class="glass-surface rounded-[var(--radius-sm)] px-3 py-2 text-sm" style="color: var(--text-primary)"></textarea>
		<input placeholder="Hilfetext / Beschreibung (optional)" bind:value={form.help} class="glass-surface rounded-[var(--radius-sm)] px-3 py-2 text-xs" style="color: var(--text-primary)" />

		{#if form.type === 'likert'}
			<div class="flex flex-wrap items-center gap-2 text-xs" style="color: var(--text-secondary)">
				<span>Skala mit</span>
				{#each [4, 5, 6, 7] as n}
					<button onclick={() => setScale(n)} class="rounded-full px-3 py-1" style="background: {form.scaleMax === n ? 'var(--accent)' : 'var(--surface-glass-strong)'}; color: {form.scaleMax === n ? 'var(--accent-contrast)' : 'var(--text-primary)'}">{n} Stufen</button>
				{/each}
			</div>
			<p class="text-xs" style="color: var(--text-muted)">Beschriftung jeder Stufe (so sehen es die Teilnehmenden):</p>
			<ol class="flex flex-col gap-2">
				{#each form.labels as _l, i}
					<li class="flex items-center gap-2"><span class="w-6 text-center text-xs" style="color: var(--text-muted)">{i + 1}</span>
						<input bind:value={form.labels[i]} placeholder={`Stufe ${i + 1}`} class="glass-surface flex-1 rounded-[var(--radius-sm)] px-3 py-2 text-sm" style="color: var(--text-primary)" /></li>
				{/each}
			</ol>
		{/if}
		{#if form.type === 'nps'}
			<div class="grid gap-2 sm:grid-cols-2">
				<input placeholder="Beschriftung 0" bind:value={form.poleMin} class="glass-surface rounded-[var(--radius-sm)] px-3 py-2 text-sm" />
				<input placeholder="Beschriftung 10" bind:value={form.poleMax} class="glass-surface rounded-[var(--radius-sm)] px-3 py-2 text-sm" />
			</div>
		{/if}
		{#if form.type === 'choice'}
			<p class="text-xs" style="color: var(--text-muted)">Antwortoptionen ({form.allowMultiple ? 'mehrere auswählbar' : 'genau eine auswählbar'}):</p>
			<ol class="flex flex-col gap-2">
				{#each form.options as _o, i}
					<li class="flex items-center gap-2">
						<span class="w-6 text-center" style="color: var(--text-muted)">{form.allowMultiple ? '☐' : '○'}</span>
						<input bind:value={form.options[i]} placeholder={`Option ${i + 1}`} class="glass-surface flex-1 rounded-[var(--radius-sm)] px-3 py-2 text-sm" style="color: var(--text-primary)" />
						{#if form.options.length > 2}<button onclick={() => form.options.splice(i, 1)} class="px-2 text-sm" style="color: var(--danger)" aria-label="Option entfernen">✕</button>{/if}
					</li>
				{/each}
			</ol>
			<button onclick={() => form.options.push('')} class="self-start text-sm" style="color: var(--accent)">+ Option hinzufügen</button>
			<label class="flex items-center gap-2 text-xs" style="color: var(--text-secondary)">
				<input type="checkbox" bind:checked={form.allowMultiple} /> Mehrfachantworten möglich
			</label>
		{/if}

		<label class="flex items-center gap-2 text-xs" style="color: var(--text-secondary)">
			<input type="checkbox" bind:checked={form.mandatory} /> Pflichtfrage
		</label>

		<label class="flex items-center gap-2 text-xs" style="color: var(--text-secondary)">
			<input type="checkbox" bind:checked={form.branching} disabled={branchSources.length === 0} /> Verzweigung: nur anzeigen, wenn …
		</label>
		{#if form.branching}
			<div class="flex flex-wrap items-center gap-2 text-xs" style="color: var(--text-secondary)">
				<select bind:value={form.showIfQuestion} class="glass-surface max-w-[18rem] rounded px-2 py-1">
					<option value={null}>Bezugsfrage wählen</option>
					{#each branchSources as s (s.id)}<option value={s.id}>{s.text.slice(0, 60)}</option>{/each}
				</select>
				<select bind:value={form.showIfOp} class="glass-surface rounded px-2 py-1">
					{#each Object.entries(OPERATORS) as [k, v]}<option value={k}>{v}</option>{/each}
				</select>
				{#if sourceQuestion?.type === 'choice'}
					<select bind:value={form.showIfValue} class="glass-surface rounded px-2 py-1">
						<option value="">Option wählen</option>
						{#each sourceQuestion.options ?? [] as o}<option value={o}>{o}</option>{/each}
					</select>
				{:else}
					<input placeholder="Wert (z. B. 7)" bind:value={form.showIfValue} class="glass-surface w-24 rounded px-2 py-1" />
				{/if}
			</div>
		{/if}

		<div class="flex gap-2">
			<Button variant="primary" onclick={submitAddForm}>Hinzufügen</Button>
			<Button variant="secondary" onclick={() => (addFormOpenFor = undefined)}>Abbrechen</Button>
		</div>
	</div>
{/snippet}

{#if detail}
	<div class="mb-6 flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-2xl font-bold" style="color: var(--text-primary)">{detail.survey_template_name}</h1>
			<p class="text-sm" style="color: var(--text-secondary)">
				Version {detail.version_number}
				<span class="ml-2 rounded-full px-2 py-0.5 text-xs" style="background: {isLocked ? 'var(--text-muted)' : 'var(--success)'}; color: white">{isLocked ? 'Gesperrt' : 'Entwurf'}</span>
				{#if detail.limesurvey_template_sid}<span class="ml-2 text-xs" style="color: var(--text-muted)">LimeSurvey-ID: {detail.limesurvey_template_sid}</span>{/if}
				· {detail.questions.length} Fragen
			</p>
		</div>
		<div class="flex gap-2">
			<Button variant="secondary" onclick={() => (showPreview = !showPreview)}>{showPreview ? 'Bearbeiten' : 'Vorschau'}</Button>
			{#if isLocked}<Button variant="primary" onclick={cloneVersion}>Als neue Version bearbeiten</Button>{/if}
			<Button variant="primary" onclick={transfer} disabled={transferring}>Veröffentlichen</Button>
		</div>
	</div>

	{#if error}<p class="mb-3 text-sm" style="color: var(--danger)">{error}</p>{/if}
	{#if transferMessage}<p class="mb-4 text-sm" style="color: var(--text-secondary)">{transferMessage}</p>{/if}

	{#if isLocked && !showPreview}
		<Card>
			<p style="color: var(--text-secondary)">
				Diese Version wird bereits in einer Befragungsrunde verwendet und ist daher gesperrt. Klicken Sie „Als neue Version bearbeiten“, um Änderungen vorzunehmen.
			</p>
		</Card>
	{/if}

	<div class="flex flex-col gap-4">
		{#each [...detail.dimensions].sort((a, b) => a.sort_order - b.sort_order) as dim (dim.id)}
			<Card>
				<div class="mb-3 flex items-center justify-between">
					<h2 class="text-lg font-semibold" style="color: var(--text-primary)">{dim.name}</h2>
					{#if editable}<button onclick={() => deleteDimension(dim.id)} class="text-xs" style="color: var(--danger)">Dimension löschen</button>{/if}
				</div>
				<div role="list" ondragover={(e) => e.preventDefault()} ondrop={() => onDrop(dim.id, questionsFor(dim.id).length)} class="flex flex-col gap-2">
					{#each questionsFor(dim.id) as q, idx (q.id)}{@render questionRow(q, dim.id, idx)}{/each}
				</div>
				{#if editable}
					{#if addFormOpenFor === dim.id}{@render addForm()}{:else}
						<button onclick={() => openAddForm(dim.id)} class="mt-3 text-sm" style="color: var(--accent)">+ Frage hinzufügen</button>
					{/if}
				{/if}
			</Card>
		{/each}

		<Card title="Weitere Fragen (NPS, Auswahl, Freitext …)">
			<div role="list" ondragover={(e) => e.preventDefault()} ondrop={() => onDrop(null, questionsFor(null).length)} class="flex flex-col gap-2">
				{#each questionsFor(null) as q, idx (q.id)}{@render questionRow(q, null, idx)}{/each}
			</div>
			{#if editable}
				{#if addFormOpenFor === null}{@render addForm()}{:else}
					<button onclick={() => openAddForm(null)} class="mt-3 text-sm" style="color: var(--accent)">+ Frage hinzufügen</button>
				{/if}
			{/if}
		</Card>

		{#if editable}
			<Card>
				<div class="flex gap-2">
					<input type="text" placeholder="Name der neuen Dimension" bind:value={newDimensionName} class="glass-surface flex-1 rounded-[var(--radius-sm)] px-3 py-2 text-sm" style="color: var(--text-primary)" />
					<Button onclick={addDimension} disabled={!newDimensionName.trim()}>Dimension hinzufügen</Button>
				</div>
			</Card>
		{/if}
	</div>
{:else if error}
	<Card><p style="color: var(--danger)">{error}</p></Card>
{:else}
	<p style="color: var(--text-secondary)">Lädt…</p>
{/if}
