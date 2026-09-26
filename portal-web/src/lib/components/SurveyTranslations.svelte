<script lang="ts">
	// Übersetzungsansicht des Fragebogen-Editors: links/oben die deutsche Fassung, darunter die Felder der Zielsprache.
	// Leere Felder fallen beim Ausspielen auf Deutsch zurück. Speichern beim Verlassen eines Feldes.
	import { surveysApi, type Question, type QuestionTranslation, type SurveyVersionDetail } from '$lib/api/surveys';
	import { ApiError } from '$lib/api/client';

	let {
		detail,
		lang,
		langName,
		editable,
		onchanged
	}: { detail: SurveyVersionDetail; lang: string; langName: string; editable: boolean; onchanged: () => Promise<void> | void } = $props();

	let error = $state('');
	let saving = $state('');
	let aiBusy = $state(false);
	let aiMsg = $state('');

	const tr = (q: Question): QuestionTranslation => q.translations?.[lang] ?? {};
	const dimOf = (id: number | null) => detail.dimensions.find((d) => d.id === id);
	const ordered = $derived([...detail.questions].sort((a, b) => a.sort_order - b.sort_order));

	// Fortschritt: uebersetzte Fragen (Text vorhanden) + Dimensionen
	const done = $derived(ordered.filter((q) => (tr(q).text ?? '').trim()).length + detail.dimensions.filter((d) => (d.translations?.[lang]?.name ?? '').trim()).length);
	const total = $derived(ordered.length + detail.dimensions.length);

	async function run(key: string, fn: () => Promise<unknown>) {
		error = '';
		saving = key;
		try {
			await fn();
			await onchanged();
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Speichern fehlgeschlagen';
		} finally {
			saving = '';
		}
	}
	function saveField(q: Question, field: keyof QuestionTranslation, value: string) {
		if ((tr(q)[field] as string | undefined ?? '') === value.trim()) return;
		return run(`q${q.id}${field}`, () => surveysApi.setQuestionTranslation(q.id, lang, { [field]: value.trim() }));
	}
	function saveList(q: Question, field: 'options' | 'scale_labels', idx: number, value: string, count: number) {
		const cur = [...((tr(q)[field] as string[] | undefined) ?? Array(count).fill(''))];
		while (cur.length < count) cur.push('');
		if (cur[idx] === value.trim()) return;
		cur[idx] = value.trim();
		// Nur speichern, wenn alle Eintraege gefuellt sind (sonst fehlende Eintraege -> Deutsch); Teilstand lokal merken
		return run(`q${q.id}${field}${idx}`, () => surveysApi.setQuestionTranslation(q.id, lang, { [field]: cur }));
	}
	async function autoTranslate() {
		aiBusy = true;
		aiMsg = '';
		error = '';
		try {
			const r = await surveysApi.autoTranslate(detail.id, lang);
			aiMsg = `${r.translated} Einträge vorgeschlagen – bitte prüfen.`;
			await onchanged();
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Automatische Übersetzung nicht möglich';
		} finally {
			aiBusy = false;
		}
	}
	const listVal = (q: Question, field: 'options' | 'scale_labels', i: number) => ((tr(q)[field] as string[] | undefined) ?? [])[i] ?? '';
</script>

<div class="mb-4 flex flex-wrap items-center gap-3">
	<div class="min-w-0 flex-1">
		<p class="font-semibold" style="color: var(--text-primary)">Übersetzung: {langName}</p>
		<div class="mt-1 h-2 overflow-hidden rounded-full" style="background: var(--border-subtle)" role="progressbar" aria-valuenow={total ? Math.round((done / total) * 100) : 0} aria-valuemin="0" aria-valuemax="100">
			<div class="h-2 rounded-full" style="width:{total ? (done / total) * 100 : 0}%; background: var(--success)"></div>
		</div>
		<p class="mt-1 text-xs" style="color: var(--text-secondary)">{done} von {total} übersetzt · Nicht übersetzte Felder erscheinen für Teilnehmende auf Deutsch.</p>
	</div>
	{#if editable}
		<button class="ai" onclick={autoTranslate} disabled={aiBusy}>{aiBusy ? 'Übersetze …' : '✨ Fehlendes mit KI übersetzen'}</button>
	{/if}
</div>
{#if error}<p class="mb-3 text-sm" style="color: var(--danger)">{error}</p>{/if}
{#if aiMsg}<p class="mb-3 text-sm" style="color: var(--success)">{aiMsg}</p>{/if}
{#if !editable}<p class="mb-3 text-sm" style="color: var(--warning)">Diese Version ist gesperrt. Über „Als neue Version bearbeiten“ kannst du Übersetzungen ändern.</p>{/if}

<div class="flex flex-col gap-4">
	{#each detail.dimensions as d (d.id)}
		<div class="glass-surface p-4">
			<p class="text-xs" style="color: var(--text-muted)">Thema · Deutsch</p>
			<p class="mb-2 font-semibold" style="color: var(--text-primary)">{d.name}</p>
			<input class="fld" disabled={!editable} placeholder={`${langName}: Name des Themas`} value={d.translations?.[lang]?.name ?? ''}
				onblur={(e) => run(`d${d.id}`, () => surveysApi.setDimensionTranslation(d.id, lang, e.currentTarget.value))} />
		</div>
	{/each}

	{#each ordered as q (q.id)}
		<div class="glass-surface p-4">
			<p class="text-xs" style="color: var(--text-muted)">{dimOf(q.dimension_id)?.name ?? 'Weitere Fragen'} · Deutsch</p>
			<p class="mb-2" style="color: var(--text-primary)">{q.text}</p>
			<textarea class="fld" rows="2" disabled={!editable} placeholder={`${langName}: Fragetext`} value={tr(q).text ?? ''}
				onblur={(e) => saveField(q, 'text', e.currentTarget.value)}></textarea>

			{#if q.help_text}
				<p class="mt-3 text-xs" style="color: var(--text-muted)">Hilfetext · Deutsch: {q.help_text}</p>
				<input class="fld" disabled={!editable} placeholder={`${langName}: Hilfetext`} value={tr(q).help_text ?? ''} onblur={(e) => saveField(q, 'help_text', e.currentTarget.value)} />
			{/if}

			{#if q.type === 'likert' && q.scale_labels?.length}
				<p class="mt-3 text-xs" style="color: var(--text-muted)">Beschriftung der Stufen</p>
				<ol class="flex flex-col gap-2">
					{#each q.scale_labels as base, i}
						<li class="pair"><span class="src">{i + 1} · {base}</span>
							<input class="fld" disabled={!editable} placeholder={`${langName}`} value={listVal(q, 'scale_labels', i)} onblur={(e) => saveList(q, 'scale_labels', i, e.currentTarget.value, q.scale_labels!.length)} /></li>
					{/each}
				</ol>
			{/if}

			{#if q.type === 'nps'}
				<div class="mt-3 grid gap-2 sm:grid-cols-2">
					<div><p class="src">0 · {q.pole_label_min || 'Sehr unwahrscheinlich'}</p><input class="fld" disabled={!editable} placeholder={langName} value={tr(q).pole_label_min ?? ''} onblur={(e) => saveField(q, 'pole_label_min', e.currentTarget.value)} /></div>
					<div><p class="src">10 · {q.pole_label_max || 'Sehr wahrscheinlich'}</p><input class="fld" disabled={!editable} placeholder={langName} value={tr(q).pole_label_max ?? ''} onblur={(e) => saveField(q, 'pole_label_max', e.currentTarget.value)} /></div>
				</div>
			{/if}

			{#if q.type === 'choice' && q.options?.length}
				<p class="mt-3 text-xs" style="color: var(--text-muted)">Antwortoptionen</p>
				<ol class="flex flex-col gap-2">
					{#each q.options as base, i}
						<li class="pair"><span class="src">{q.allow_multiple ? '☐' : '○'} {base}</span>
							<input class="fld" disabled={!editable} placeholder={`${langName}`} value={listVal(q, 'options', i)} onblur={(e) => saveList(q, 'options', i, e.currentTarget.value, q.options!.length)} /></li>
					{/each}
				</ol>
			{/if}
			{#if saving.startsWith(`q${q.id}`)}<p class="mt-1 text-xs" style="color: var(--text-muted)">Speichere …</p>{/if}
		</div>
	{/each}
</div>

<style>
	.fld {
		width: 100%;
		border-radius: var(--radius-sm);
		padding: 0.55rem 0.75rem;
		font-size: 0.9rem;
		background: var(--surface-glass-strong);
		border: 1px solid var(--border-subtle);
		color: var(--text-primary);
	}
	.fld:disabled {
		opacity: 0.6;
	}
	.pair {
		display: grid;
		gap: 0.25rem;
	}
	@media (min-width: 640px) {
		.pair {
			grid-template-columns: 1fr 1fr;
			align-items: center;
			gap: 0.75rem;
		}
	}
	.src {
		font-size: 0.8rem;
		color: var(--text-secondary);
	}
	.ai {
		min-height: 44px;
		padding: 0 1rem;
		border-radius: var(--radius-sm);
		background: var(--surface-glass-strong);
		border: 1px solid var(--border-subtle);
		color: var(--accent);
		font-size: 0.85rem;
		font-weight: 600;
	}
</style>
