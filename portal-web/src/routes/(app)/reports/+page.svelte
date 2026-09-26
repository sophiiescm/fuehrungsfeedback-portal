<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import { api } from '$lib/api/client';
	import { downloadPdf } from '$lib/api/rounds';

	interface Dim {
		dimension: string;
		mean: number;
		median: number;
		stddev: number;
		min: number;
		max: number;
		n: number;
		distribution: Record<string, number>;
		fachbereich: { mean: number } | null;
		unternehmen: { mean: number } | null;
		vorrunde: { mean: number; delta: number } | null;
	}
	interface Question {
		question: string;
		type: string;
		options: string[] | null;
		n: number;
		mean: number | null;
		distribution: Record<string, number>;
	}
	interface Nps {
		score: number | null;
		n: number;
		promoters: number;
		passives: number;
		detractors: number;
	}
	interface Detail {
		available: boolean;
		message?: string;
		round_name: string;
		n_responses: number;
		dimensions?: Dim[];
		questions?: Question[];
		nps?: Nps | null;
		nps_reference?: { value: number | null; label: string } | null;
		freetext?: { question: string; texts: string[] }[];
		categories?: { category: string; count: number; texts: string[] }[];
		wordcloud?: { word: string; count: number }[];
		ai_summary?: string | null;
	}

	let list = $state<{ target_id: number; round_name: string; start: string }[]>([]);
	let detail = $state<Detail | null>(null);
	let selected = $state<number | null>(null);
	let trend = $state<Record<string, { round: string; mean: number }[]>>({});
	let textTab = $state<'kategorien' | 'wordcloud' | 'alle'>('kategorien');

	onMount(async () => {
		list = await api.get('/reports/mine');
		trend = (await api.get<{ series: typeof trend }>('/reports/mine/trend')).series;
		if (list.length) open(list[0].target_id);
	});
	async function open(id: number) {
		selected = id;
		detail = await api.get<Detail>(`/reports/${id}`);
	}

	const overall = $derived(
		detail?.dimensions?.length
			? detail.dimensions.reduce((s, d) => s + d.mean, 0) / detail.dimensions.length
			: null
	);
	const overallPrev = $derived(
		detail?.dimensions?.length && detail.dimensions.every((d) => d.vorrunde)
			? detail.dimensions.reduce((s, d) => s + d.vorrunde!.mean, 0) / detail.dimensions.length
			: null
	);

	function ampel(d: Dim) {
		if (!d.unternehmen) return { color: 'var(--text-muted)', label: 'kein Vergleich' };
		const delta = d.mean - d.unternehmen.mean;
		if (delta >= 0.2) return { color: 'var(--success)', label: 'über Unternehmen' };
		if (delta <= -0.2) return { color: 'var(--danger)', label: 'unter Unternehmen' };
		return { color: 'var(--warning)', label: 'im Unternehmensschnitt' };
	}
	const pct = (v: number) => `${Math.max(0, Math.min(100, (v / 5) * 100))}%`;
	const maxCount = (dist: Record<string, number>) => Math.max(1, ...Object.values(dist));

	const colors = ['#4f46e5', '#0891b2', '#16a34a', '#d97706', '#dc2626'];
	const rounds = $derived([...new Set(Object.values(trend).flatMap((s) => s.map((p) => p.round)))]);
	const x = (i: number) => 40 + (rounds.length > 1 ? (i * 520) / (rounds.length - 1) : 260);
	const y = (v: number) => 180 - ((v - 1) / 4) * 160;
	const cloudSize = (c: number, max: number) => 0.85 + (c / max) * 1.6;
</script>

<div class="mb-6 flex flex-wrap items-center justify-between gap-3">
	<h1 class="text-2xl font-bold" style="color: var(--text-primary)">Meine Reports / Trend</h1>
	{#if detail?.available}
		<Button onclick={() => downloadPdf(`/reports/${selected}/pdf`, 'report.pdf')}>⬇ Report als PDF</Button>
	{/if}
</div>

{#if list.length === 0}
	<Card><p style="color: var(--text-secondary)">Noch kein Report verfügbar.</p></Card>
{/if}

<div class="mb-5 flex flex-wrap gap-2" role="tablist" aria-label="Befragungsrunden">
	{#each list as r (r.target_id)}
		<button
			role="tab"
			aria-selected={selected === r.target_id}
			onclick={() => open(r.target_id)}
			class="rounded-full px-4 py-2 text-sm"
			style="background: {selected === r.target_id ? 'var(--accent)' : 'var(--surface-glass-strong)'}; color: {selected === r.target_id ? 'var(--accent-contrast)' : 'var(--text-primary)'}"
		>
			{r.round_name}
		</button>
	{/each}
</div>

{#if detail}
	{#if !detail.available}
		<Card title="Kein Report"><p style="color: var(--text-primary)">{detail.message}</p></Card>
	{:else}
		<div class="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
			<Card>
				<p class="text-xs" style="color: var(--text-muted)">Antworten</p>
				<p class="text-3xl font-bold" style="color: var(--text-primary)">{detail.n_responses}</p>
			</Card>
			<Card>
				<p class="text-xs" style="color: var(--text-muted)">Gesamt (Ø aller Dimensionen)</p>
				<p class="text-3xl font-bold" style="color: var(--text-primary)">{overall?.toFixed(2) ?? '–'}</p>
				{#if overall !== null && overallPrev !== null}
					<p class="text-xs" style="color: {overall >= overallPrev ? 'var(--success)' : 'var(--danger)'}">
						{overall >= overallPrev ? '▲' : '▼'} {(overall - overallPrev).toFixed(2)} zur Vorrunde
					</p>
				{/if}
			</Card>
			<Card>
				<p class="text-xs" style="color: var(--text-muted)">Net Promoter Score</p>
				<p class="text-3xl font-bold" style="color: var(--text-primary)">{detail.nps?.score ?? '–'}</p>
				{#if detail.nps_reference?.value != null && detail.nps?.score != null}
					<p class="text-xs" style="color: var(--text-secondary)">
						Referenz {detail.nps_reference.label}: {detail.nps_reference.value}
					</p>
				{/if}
			</Card>
			<Card>
				<p class="text-xs" style="color: var(--text-muted)">Bester / schwächster Bereich</p>
				{#if detail.dimensions?.length}
					{@const sorted = [...detail.dimensions].sort((a, b) => b.mean - a.mean)}
					<p class="text-sm" style="color: var(--success)">▲ {sorted[0].dimension} ({sorted[0].mean.toFixed(2)})</p>
					<p class="text-sm" style="color: var(--danger)">▼ {sorted.at(-1)?.dimension} ({sorted.at(-1)?.mean.toFixed(2)})</p>
				{/if}
			</Card>
		</div>

		<h2 class="mb-3 text-lg font-semibold" style="color: var(--text-primary)">Dimensionen im Vergleich</h2>
		<div class="grid gap-4 md:grid-cols-2">
			{#each detail.dimensions ?? [] as d (d.dimension)}
				{@const a = ampel(d)}
				<Card>
					<div class="flex items-start justify-between">
						<div>
							<p class="font-semibold" style="color: var(--text-primary)">{d.dimension}</p>
							<p class="text-xs" style="color: {a.color}">● {a.label}</p>
						</div>
						<p class="text-3xl font-bold" style="color: var(--text-primary)">{d.mean.toFixed(2)}</p>
					</div>
					<div class="mt-3 space-y-1 text-xs" style="color: var(--text-secondary)">
						{#each [{ label: 'Ich', v: d.mean, c: 'var(--accent)' }, { label: 'Fachbereich', v: d.fachbereich?.mean, c: 'var(--warning)' }, { label: 'Unternehmen', v: d.unternehmen?.mean, c: 'var(--success)' }, { label: 'Vorrunde', v: d.vorrunde?.mean, c: 'var(--text-muted)' }] as row (row.label)}
							<div class="flex items-center gap-2">
								<span class="w-24 shrink-0">{row.label}</span>
								<div class="h-2 flex-1 rounded" style="background: var(--border-subtle)">
									{#if row.v != null}<div class="h-2 rounded" style="width:{pct(row.v)}; background:{row.c}"></div>{/if}
								</div>
								<span class="w-10 text-right">{row.v != null ? row.v.toFixed(2) : '–'}</span>
							</div>
						{/each}
					</div>
					<div class="mt-3 flex items-end gap-1" aria-label="Verteilung der Antworten">
						{#each Object.entries(d.distribution) as [k, v] (k)}
							<div class="text-center text-[10px]" style="color: var(--text-muted)">
								<div style="height:{Math.max(3, (v / maxCount(d.distribution)) * 36)}px; width:16px; background: var(--accent); opacity:.55"></div>
								{k}
							</div>
						{/each}
						<span class="ml-auto text-[10px]" style="color: var(--text-muted)">Median {d.median} · σ {d.stddev}</span>
					</div>
				</Card>
			{/each}
		</div>

		{#if detail.nps && detail.nps.n > 0}
			<div class="mt-6">
				<Card title="Net Promoter Score">
					<div class="flex h-6 overflow-hidden rounded" role="img" aria-label="Promoter, Passive, Detractors">
						<div style="width:{(detail.nps.detractors / detail.nps.n) * 100}%; background: var(--danger)"></div>
						<div style="width:{(detail.nps.passives / detail.nps.n) * 100}%; background: var(--warning)"></div>
						<div style="width:{(detail.nps.promoters / detail.nps.n) * 100}%; background: var(--success)"></div>
					</div>
					<p class="mt-2 text-xs" style="color: var(--text-secondary)">
						Detractors {detail.nps.detractors} · Passive {detail.nps.passives} · Promoter {detail.nps.promoters} → NPS {detail.nps.score}
					</p>
				</Card>
			</div>
		{/if}

		{#if detail.questions?.some((q) => q.type === 'choice')}
			<h2 class="mt-6 mb-3 text-lg font-semibold" style="color: var(--text-primary)">Auswahlfragen</h2>
			<div class="grid gap-4 md:grid-cols-2">
				{#each detail.questions.filter((q) => q.type === 'choice') as q (q.question)}
					<Card title={q.question}>
						{#each Object.entries(q.distribution) as [opt, cnt] (opt)}
							<div class="mb-1 flex items-center gap-2 text-xs" style="color: var(--text-secondary)">
								<span class="w-32 shrink-0">{opt}</span>
								<div class="h-2 flex-1 rounded" style="background: var(--border-subtle)">
									<div class="h-2 rounded" style="width:{(cnt / q.n) * 100}%; background: var(--accent)"></div>
								</div>
								<span class="w-8 text-right">{cnt}</span>
							</div>
						{/each}
						<p class="text-[10px]" style="color: var(--text-muted)">{q.n} Personen haben geantwortet</p>
					</Card>
				{/each}
			</div>
		{/if}

		{#if detail.ai_summary}
			<div class="mt-6">
				<Card title="Zusammenfassung der Freitexte (KI)">
					<p class="text-sm whitespace-pre-line" style="color: var(--text-primary)">{detail.ai_summary}</p>
				</Card>
			</div>
		{/if}

		{#if detail.freetext?.length}
			<div class="mt-6">
				<Card title="Freitext-Rückmeldungen (geschwärzt, nicht rückverfolgbar)">
					<div class="mb-3 flex gap-2 text-sm">
						{#each [['kategorien', 'Kategorien'], ['wordcloud', 'Wordcloud'], ['alle', 'Alle Antworten']] as [id, label] (id)}
							<button
								onclick={() => (textTab = id as typeof textTab)}
								class="rounded-full px-3 py-1"
								style="background: {textTab === id ? 'var(--accent)' : 'var(--surface-glass-strong)'}; color: {textTab === id ? 'var(--accent-contrast)' : 'var(--text-primary)'}"
							>{label}</button>
						{/each}
					</div>
					{#if textTab === 'kategorien'}
						{#each detail.categories ?? [] as c (c.category)}
							<details class="mb-2" open>
								<summary class="cursor-pointer text-sm font-semibold" style="color: var(--text-primary)">{c.category} ({c.count})</summary>
								<ul class="ml-5 list-disc text-sm" style="color: var(--text-secondary)">{#each c.texts as t}<li>{t}</li>{/each}</ul>
							</details>
						{:else}
							<p class="text-sm" style="color: var(--text-secondary)">Zu wenige Antworten je Kategorie, um sie anzuzeigen.</p>
						{/each}
					{:else if textTab === 'wordcloud'}
						<div class="flex flex-wrap items-center gap-x-4 gap-y-1" role="img" aria-label="Wordcloud">
							{#each detail.wordcloud ?? [] as w (w.word)}
								{@const max = detail.wordcloud?.[0].count ?? 1}
								<span style="font-size:{cloudSize(w.count, max)}rem; color: var(--accent); opacity:{0.55 + (w.count / max) * 0.45}" title="{w.count} Antworten">{w.word}</span>
							{:else}
								<p class="text-sm" style="color: var(--text-secondary)">Noch keine Wörter, die in mindestens 3 verschiedenen Antworten vorkommen.</p>
							{/each}
						</div>
					{:else}
						{#each detail.freetext as g (g.question)}
							<p class="mt-2 text-sm font-semibold" style="color: var(--text-primary)">{g.question}</p>
							<ul class="ml-5 list-disc text-sm" style="color: var(--text-secondary)">{#each g.texts as t}<li>{t}</li>{/each}</ul>
						{/each}
					{/if}
				</Card>
			</div>
		{/if}
	{/if}
{/if}

{#if rounds.length > 0}
	<div class="mt-6">
		<Card title="Trend über alle Runden">
			<svg viewBox="0 0 600 220" class="w-full" role="img" aria-label="Verlauf der Dimensionen">
				{#each [1, 2, 3, 4, 5] as g}
					<line x1="40" x2="580" y1={y(g)} y2={y(g)} stroke="currentColor" opacity=".15" />
					<text x="10" y={y(g) + 4} font-size="10" fill="currentColor">{g}</text>
				{/each}
				{#each rounds as r, i}<text x={x(i)} y="212" font-size="9" text-anchor="middle" fill="currentColor">{r}</text>{/each}
				{#each Object.entries(trend) as [name, pts], si (name)}
					<polyline fill="none" stroke={colors[si % 5]} stroke-width="2" points={pts.map((p) => `${x(rounds.indexOf(p.round))},${y(p.mean)}`).join(' ')} />
				{/each}
			</svg>
			<div class="flex flex-wrap gap-3 text-xs" style="color: var(--text-secondary)">
				{#each Object.keys(trend) as name, si (name)}<span><span style="color:{colors[si % 5]}">■</span> {name}</span>{/each}
			</div>
		</Card>
	</div>
{/if}
