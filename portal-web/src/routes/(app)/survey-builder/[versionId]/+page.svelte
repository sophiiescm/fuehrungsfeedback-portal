<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import { surveysApi, type SurveyVersionDetail, type Question } from '$lib/api/surveys';
	import { ApiError } from '$lib/api/client';

	const versionId = $derived(Number(page.params.versionId));

	let detail = $state<SurveyVersionDetail | null>(null);
	let error = $state('');
	let showPreview = $state(false);
	let newDimensionName = $state('');
	let draggedQuestionId = $state<number | null>(null);
	let transferring = $state(false);
	let transferMessage = $state('');

	// Formular fuer "Frage hinzufuegen", pro Sektion (dimensionId oder null) geoeffnet
	let addFormOpenFor = $state<number | null | undefined>(undefined);
	let formType = $state<'likert' | 'freitext'>('likert');
	let formText = $state('');
	let formScaleMin = $state(1);
	let formScaleMax = $state(5);
	let formPoleMin = $state('Trifft gar nicht zu');
	let formPoleMax = $state('Trifft voll zu');
	let formMandatory = $state(true);

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

	function questionsFor(dimensionId: number | null): Question[] {
		if (!detail) return [];
		return detail.questions
			.filter((q) => q.dimension_id === dimensionId)
			.sort((a, b) => a.sort_order - b.sort_order);
	}

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
		formType = dimensionId === null ? 'freitext' : 'likert';
		formText = '';
		formScaleMin = 1;
		formScaleMax = 5;
		formPoleMin = 'Trifft gar nicht zu';
		formPoleMax = 'Trifft voll zu';
		formMandatory = true;
	}

	async function submitAddForm() {
		if (!detail || !formText.trim() || addFormOpenFor === undefined) return;
		await surveysApi.addQuestion(detail.id, {
			type: formType,
			text: formText.trim(),
			dimension_id: addFormOpenFor,
			scale_min: formScaleMin,
			scale_max: formScaleMax,
			pole_label_min: formPoleMin,
			pole_label_max: formPoleMax,
			mandatory: formMandatory
		});
		addFormOpenFor = undefined;
		await load();
	}

	async function deleteQuestion(id: number) {
		await surveysApi.deleteQuestion(id);
		await load();
	}

	async function toggleMandatory(q: Question) {
		await surveysApi.updateQuestion(q.id, { mandatory: !q.mandatory });
		await load();
	}

	function onDragStart(questionId: number) {
		draggedQuestionId = questionId;
	}

	async function onDrop(targetDimensionId: number | null, targetIndex: number) {
		if (!detail || draggedQuestionId === null) return;
		const dragged = detail.questions.find((q) => q.id === draggedQuestionId);
		if (!dragged) return;

		// Neue lokale Reihenfolge innerhalb der Zielsektion berechnen
		const targetQuestions = questionsFor(targetDimensionId).filter((q) => q.id !== draggedQuestionId);
		targetQuestions.splice(targetIndex, 0, { ...dragged, dimension_id: targetDimensionId });

		// Alle anderen Sektionen unveraendert lassen, nur die Zielsektion neu nummerieren,
		// und global fortlaufende sort_order ueber alle Sektionen vergeben.
		const sections = [
			...detail.dimensions.map((d) => d.id),
			null // "Weitere Fragen"
		];
		let order = 1;
		const payload: { id: number; dimension_id: number | null; sort_order: number }[] = [];
		for (const sectionId of sections) {
			const qs = sectionId === targetDimensionId ? targetQuestions : questionsFor(sectionId);
			for (const q of qs) {
				payload.push({ id: q.id, dimension_id: sectionId, sort_order: order++ });
			}
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
			transferMessage = `Übertragen (LimeSurvey-ID ${result.limesurvey_template_sid}).`;
			await load();
		} catch (e) {
			transferMessage = e instanceof ApiError ? e.message : 'Übertragung fehlgeschlagen';
		} finally {
			transferring = false;
		}
	}
</script>

{#if error}
	<Card>
		<p style="color: var(--danger)">{error}</p>
	</Card>
{:else if detail}
	<div class="mb-6 flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-2xl font-bold" style="color: var(--text-primary)">
				{detail.survey_template_name}
			</h1>
			<p class="text-sm" style="color: var(--text-secondary)">
				Version {detail.version_number}
				<span
					class="ml-2 rounded-full px-2 py-0.5 text-xs"
					style="background: {isLocked ? 'var(--text-muted)' : 'var(--success)'}; color: white"
				>
					{isLocked ? 'Gesperrt' : 'Entwurf'}
				</span>
				{#if detail.limesurvey_template_sid}
					<span class="ml-2 text-xs" style="color: var(--text-muted)"
						>LimeSurvey-ID: {detail.limesurvey_template_sid}</span
					>
				{/if}
			</p>
		</div>
		<div class="flex gap-2">
			<Button variant="secondary" onclick={() => (showPreview = !showPreview)}>
				{showPreview ? 'Bearbeiten' : 'Vorschau'}
			</Button>
			{#if isLocked}
				<Button variant="primary" onclick={cloneVersion}>Als neue Version bearbeiten</Button>
			{/if}
			<Button variant="primary" onclick={transfer} disabled={transferring}>
				An LimeSurvey übertragen
			</Button>
		</div>
	</div>

	{#if transferMessage}
		<p class="mb-4 text-sm" style="color: var(--text-secondary)">{transferMessage}</p>
	{/if}

	{#if isLocked && !showPreview}
		<Card>
			<p style="color: var(--text-secondary)">
				Diese Version wird bereits in einer Befragungsrunde verwendet und ist daher gesperrt.
				Klicken Sie "Als neue Version bearbeiten", um Änderungen vorzunehmen.
			</p>
		</Card>
	{/if}

	<div class="flex flex-col gap-4">
		{#each [...detail.dimensions].sort((a, b) => a.sort_order - b.sort_order) as dim (dim.id)}
			<Card>
				<div class="mb-3 flex items-center justify-between">
					<h2 class="text-lg font-semibold" style="color: var(--text-primary)">{dim.name}</h2>
					{#if !isLocked && !showPreview}
						<button
							onclick={() => deleteDimension(dim.id)}
							class="text-xs"
							style="color: var(--danger)"
						>
							Dimension löschen
						</button>
					{/if}
				</div>

				<div
					role="list"
					ondragover={(e) => e.preventDefault()}
					ondrop={() => onDrop(dim.id, questionsFor(dim.id).length)}
					class="flex flex-col gap-2"
				>
					{#each questionsFor(dim.id) as q, idx (q.id)}
						<div
							role="listitem"
							draggable={!isLocked && !showPreview}
							ondragstart={() => onDragStart(q.id)}
							ondragover={(e) => e.preventDefault()}
							ondrop={(e) => {
								e.stopPropagation();
								onDrop(dim.id, idx);
							}}
							class="glass-surface flex items-center gap-3 p-3"
						>
							{#if !isLocked && !showPreview}
								<span style="color: var(--text-muted)" class="cursor-grab">⠿</span>
							{/if}
							<div class="flex-1">
								{#if showPreview}
									<p class="mb-2 text-sm" style="color: var(--text-primary)">{q.text}</p>
									<div class="flex gap-3">
										{#each Array(( q.scale_max ?? 5) - (q.scale_min ?? 1) + 1) as _, i}
											{@const point = (q.scale_min ?? 1) + i}
											<label class="flex flex-col items-center text-xs" style="color: var(--text-muted)">
												<input type="radio" disabled />
												{point === q.scale_min ? q.pole_label_min : point === q.scale_max ? q.pole_label_max : point}
											</label>
										{/each}
									</div>
								{:else}
									<p class="text-sm" style="color: var(--text-primary)">
										{q.text}
										{#if q.mandatory}<span style="color: var(--danger)">*</span>{/if}
									</p>
									<p class="text-xs" style="color: var(--text-muted)">
										Skala {q.scale_min}–{q.scale_max}: "{q.pole_label_min}" … "{q.pole_label_max}"
									</p>
								{/if}
							</div>
							{#if !isLocked && !showPreview}
								<button
									onclick={() => toggleMandatory(q)}
									class="text-xs"
									style="color: var(--text-secondary)"
								>
									{q.mandatory ? 'Pflicht' : 'Optional'}
								</button>
								<button onclick={() => deleteQuestion(q.id)} class="text-xs" style="color: var(--danger)">
									Löschen
								</button>
							{/if}
						</div>
					{/each}
				</div>

				{#if !isLocked && !showPreview}
					{#if addFormOpenFor === dim.id}
						<div class="glass-surface mt-3 flex flex-col gap-2 p-3">
							<textarea
								placeholder="Frage"
								bind:value={formText}
								class="glass-surface rounded-[var(--radius-sm)] px-3 py-2 text-sm"
								style="color: var(--text-primary)"
							></textarea>
							<div class="flex gap-2">
								<label class="text-xs" style="color: var(--text-secondary)">
									Skala von
									<select bind:value={formScaleMin} class="glass-surface rounded px-1 py-0.5">
										{#each [1] as v}<option value={v}>{v}</option>{/each}
									</select>
									bis
									<select bind:value={formScaleMax} class="glass-surface rounded px-1 py-0.5">
										{#each [4, 5, 6, 7] as v}<option value={v}>{v}</option>{/each}
									</select>
								</label>
							</div>
							<div class="flex gap-2">
								<input
									placeholder="Pol-Beschriftung Minimum"
									bind:value={formPoleMin}
									class="glass-surface flex-1 rounded-[var(--radius-sm)] px-2 py-1 text-xs"
								/>
								<input
									placeholder="Pol-Beschriftung Maximum"
									bind:value={formPoleMax}
									class="glass-surface flex-1 rounded-[var(--radius-sm)] px-2 py-1 text-xs"
								/>
							</div>
							<label class="flex items-center gap-2 text-xs" style="color: var(--text-secondary)">
								<input type="checkbox" bind:checked={formMandatory} /> Pflichtfrage
							</label>
							<div class="flex gap-2">
								<Button variant="primary" onclick={submitAddForm}>Hinzufügen</Button>
								<Button variant="secondary" onclick={() => (addFormOpenFor = undefined)}>Abbrechen</Button>
							</div>
						</div>
					{:else}
						<button
							onclick={() => openAddForm(dim.id)}
							class="mt-3 text-sm"
							style="color: var(--accent)"
						>
							+ Frage hinzufügen
						</button>
					{/if}
				{/if}
			</Card>
		{/each}

		<Card title="Weitere Fragen (Freitext)">
			<div
				role="list"
				ondragover={(e) => e.preventDefault()}
				ondrop={() => onDrop(null, questionsFor(null).length)}
				class="flex flex-col gap-2"
			>
				{#each questionsFor(null) as q, idx (q.id)}
					<div
						role="listitem"
						draggable={!isLocked && !showPreview}
						ondragstart={() => onDragStart(q.id)}
						ondragover={(e) => e.preventDefault()}
						ondrop={(e) => {
							e.stopPropagation();
							onDrop(null, idx);
						}}
						class="glass-surface flex items-center gap-3 p-3"
					>
						{#if !isLocked && !showPreview}
							<span style="color: var(--text-muted)" class="cursor-grab">⠿</span>
						{/if}
						<div class="flex-1">
							{#if showPreview}
								<p class="mb-2 text-sm" style="color: var(--text-primary)">{q.text}</p>
								<textarea disabled class="glass-surface w-full rounded p-2 text-xs"></textarea>
							{:else}
								<p class="text-sm" style="color: var(--text-primary)">
									{q.text}
									{#if q.mandatory}<span style="color: var(--danger)">*</span>{/if}
								</p>
							{/if}
						</div>
						{#if !isLocked && !showPreview}
							<button onclick={() => toggleMandatory(q)} class="text-xs" style="color: var(--text-secondary)">
								{q.mandatory ? 'Pflicht' : 'Optional'}
							</button>
							<button onclick={() => deleteQuestion(q.id)} class="text-xs" style="color: var(--danger)">
								Löschen
							</button>
						{/if}
					</div>
				{/each}
			</div>

			{#if !isLocked && !showPreview}
				{#if addFormOpenFor === null}
					<div class="glass-surface mt-3 flex flex-col gap-2 p-3">
						<textarea
							placeholder="Frage"
							bind:value={formText}
							class="glass-surface rounded-[var(--radius-sm)] px-3 py-2 text-sm"
							style="color: var(--text-primary)"
						></textarea>
						<label class="flex items-center gap-2 text-xs" style="color: var(--text-secondary)">
							<input type="checkbox" bind:checked={formMandatory} /> Pflichtfrage
						</label>
						<div class="flex gap-2">
							<Button variant="primary" onclick={submitAddForm}>Hinzufügen</Button>
							<Button variant="secondary" onclick={() => (addFormOpenFor = undefined)}>Abbrechen</Button>
						</div>
					</div>
				{:else}
					<button onclick={() => openAddForm(null)} class="mt-3 text-sm" style="color: var(--accent)">
						+ Freitextfrage hinzufügen
					</button>
				{/if}
			{/if}
		</Card>

		{#if !isLocked && !showPreview}
			<Card>
				<div class="flex gap-2">
					<input
						type="text"
						placeholder="Name der neuen Dimension"
						bind:value={newDimensionName}
						class="glass-surface flex-1 rounded-[var(--radius-sm)] px-3 py-2 text-sm"
						style="color: var(--text-primary)"
					/>
					<Button onclick={addDimension} disabled={!newDimensionName.trim()}>Dimension hinzufügen</Button>
				</div>
			</Card>
		{/if}
	</div>
{:else}
	<p style="color: var(--text-secondary)">Lädt…</p>
{/if}
