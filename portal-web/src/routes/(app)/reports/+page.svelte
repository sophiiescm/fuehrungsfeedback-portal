<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import { api } from '$lib/api/client';
	import { downloadFile } from '$lib/api/rounds';

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
	interface Question { question: string; type: string; options: string[] | null; n: number; mean: number | null; distribution: Record<string, number> }
	interface Nps { score: number | null; n: number; promoters: number; passives: number; detractors: number }
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

	type Tab = 'ueberblick' | 'themen' | 'freitext' | 'verlauf';
	let list = $state<{ target_id: number; round_name: string; start: string }[]>([]);
	let detail = $state<Detail | null>(null);
	let selected = $state<number | null>(null);
	let trend = $state<Record<string, { round: string; mean: number }[]>>({});
	let tab = $state<Tab>('ueberblick');
	let textTab = $state<'kategorien' | 'wordcloud' | 'alle'>('kategorien');
	let openDim = $state<string | null>(null);
	let loaded = $state(false);
	let exportOpen = $state(false);
	let exportError = $state('');
	async function exportAs(fmt: string) {
		exportOpen = false;
		exportError = '';
		try {
			await downloadFile(`/reports/${selected}/export?format=${fmt}`, `feedback-report.${fmt}`);
		} catch (e) {
			exportError = e instanceof Error ? e.message : 'Export fehlgeschlagen';
		}
	}

	onMount(async () => {
		list = await api.get('/reports/mine');
		trend = (await api.get<{ series: typeof trend }>('/reports/mine/trend')).series;
		loaded = true;
		if (list.length) open(list[0].target_id);
	});
	async function open(id: number) {
		selected = id;
		openDim = null;
		detail = await api.get<Detail>(`/reports/${id}`);
	}

	const dims = $derived(detail?.dimensions ?? []);
	const sorted = $derived([...dims].sort((a, b) => b.mean - a.mean));
	const strengths = $derived(sorted.slice(0, 2));
	const growth = $derived([...sorted].reverse().slice(0, 2));
	const avg = (xs: number[]) => (xs.length ? xs.reduce((s, v) => s + v, 0) / xs.length : null);
	const overall = $derived(avg(dims.map((d) => d.mean)));
	const overallPrev = $derived(dims.length && dims.every((d) => d.vorrunde) ? avg(dims.map((d) => d.vorrunde!.mean)) : null);
	const overallCompany = $derived(dims.length && dims.every((d) => d.unternehmen) ? avg(dims.map((d) => d.unternehmen!.mean)) : null);
	const hasFreetext = $derived(!!detail?.freetext?.length || !!detail?.ai_summary);
	const trendRounds = $derived([...new Set(Object.values(trend).flatMap((s) => s.map((p) => p.round)))]);

	function verdict(d: Dim) {
		if (!d.unternehmen) return { color: 'var(--text-muted)', label: 'kein Vergleich', text: '' };
		const delta = d.mean - d.unternehmen.mean;
		if (delta >= 0.2) return { color: 'var(--success)', label: 'über dem Schnitt', text: `+${delta.toFixed(1)} zum Unternehmen` };
		if (delta <= -0.2) return { color: 'var(--danger)', label: 'unter dem Schnitt', text: `${delta.toFixed(1)} zum Unternehmen` };
		return { color: 'var(--warning)', label: 'im Schnitt', text: 'wie das Unternehmen' };
	}
	const pct = (v: number) => `${Math.max(0, Math.min(100, ((v - 1) / 4) * 100))}%`;
	const maxCount = (dist: Record<string, number>) => Math.max(1, ...Object.values(dist));
	const fmt = (v: number | null | undefined) => (v == null ? '–' : v.toFixed(1).replace('.', ','));
	const signed = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(1).replace('.', ',')}`;

	// Ring: Wert 1..5 als Anteil
	const R = 54;
	const C = 2 * Math.PI * R;
	const colors = ['#004f23', '#007298', '#16a34a', '#d97706', '#dc2626'];
	const x = (i: number) => 40 + (trendRounds.length > 1 ? (i * 520) / (trendRounds.length - 1) : 260);
	const y = (v: number) => 180 - ((v - 1) / 4) * 160;
	const cloudSize = (c: number, max: number) => 0.85 + (c / max) * 1.6;

	const tabs = $derived<[Tab, string][]>([
		['ueberblick', 'Überblick'],
		['themen', 'Themen'],
		...(hasFreetext ? ([['freitext', 'Freitext']] as [Tab, string][]) : []),
		['verlauf', 'Verlauf']
	]);
</script>

<!-- Kopf: Titel, Runde wählen, Aktionen -->
<div class="mb-4 flex flex-wrap items-end justify-between gap-3">
	<div>
		<h1 class="text-2xl font-bold" style="color: var(--text-primary)">Mein Feedback-Report</h1>
		<p class="text-sm" style="color: var(--text-secondary)">So sieht dein Team dich – anonym und ab 3 Antworten.</p>
	</div>
	{#if detail?.available}
		<div class="flex flex-wrap gap-2">
			<a href="/massnahmen" class="btn ghost">Maßnahmen ableiten</a>
			<div class="relative">
				<button class="btn" aria-haspopup="menu" aria-expanded={exportOpen} onclick={() => (exportOpen = !exportOpen)}>⬇ Exportieren ▾</button>
				{#if exportOpen}
					<button class="fixed inset-0 z-10 cursor-default" aria-label="Menü schließen" onclick={() => (exportOpen = false)}></button>
					<div class="glass-surface absolute right-0 z-20 mt-2 flex w-56 flex-col p-2" style="background: var(--surface-glass-strong)" role="menu">
						{#each [['pdf', '📄 PDF'], ['pptx', '📊 PowerPoint'], ['xlsx', '📈 Excel'], ['csv', '🧾 CSV']] as [f, l] (f)}
							<button class="row" role="menuitem" onclick={() => exportAs(f)}>{l}</button>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>

{#if exportError}<p class="mb-3 text-sm" style="color: var(--danger)">{exportError}</p>{/if}

{#if loaded && list.length === 0}
	<Card>
		<p class="font-semibold" style="color: var(--text-primary)">Noch kein Report verfügbar</p>
		<p class="text-sm" style="color: var(--text-secondary)">Sobald eine Befragungsrunde ausgewertet ist und mindestens 3 Personen geantwortet haben, findest du hier deinen Report.</p>
	</Card>
{/if}

{#if list.length > 1}
	<div class="mb-4 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Befragungsrunden">
		{#each list as r (r.target_id)}
			<button role="tab" aria-selected={selected === r.target_id} onclick={() => open(r.target_id)} class="chip" class:on={selected === r.target_id}>{r.round_name}</button>
		{/each}
	</div>
{/if}

{#if detail}
	{#if !detail.available}
		<Card title="Kein Report für diese Runde"><p style="color: var(--text-primary)">{detail.message}</p></Card>
	{:else}
		<!-- Bereichs-Tabs -->
		<div class="seg mb-4" role="tablist" aria-label="Bereiche des Reports">
			{#each tabs as [id, label] (id)}
				<button role="tab" aria-selected={tab === id} class:on={tab === id} onclick={() => (tab = id)}>{label}</button>
			{/each}
		</div>

		{#if tab === 'ueberblick'}
			<!-- Held: Gesamtbild -->
			<div class="glass-surface hero mb-4 p-5">
				<svg viewBox="0 0 140 140" width="132" height="132" role="img" aria-label="Gesamtwert {fmt(overall)} von 5">
					<circle cx="70" cy="70" r={R} fill="none" stroke="var(--border-subtle)" stroke-width="12" />
					<circle cx="70" cy="70" r={R} fill="none" stroke="var(--accent)" stroke-width="12" stroke-linecap="round"
						stroke-dasharray="{C * (((overall ?? 1) - 1) / 4)} {C}" transform="rotate(-90 70 70)" />
					<text x="70" y="70" text-anchor="middle" font-size="30" font-weight="700" fill="var(--text-primary)">{fmt(overall)}</text>
					<text x="70" y="90" text-anchor="middle" font-size="11" fill="var(--text-secondary)">von 5</text>
				</svg>
				<div class="flex-1">
					<p class="text-xs font-semibold tracking-wide uppercase" style="color: var(--accent-text)">{detail.round_name}</p>
					<p class="text-lg font-semibold" style="color: var(--text-primary)">
						{#if overallCompany != null && overall != null}
							{overall - overallCompany >= 0.2 ? 'Über dem Unternehmensschnitt' : overall - overallCompany <= -0.2 ? 'Unter dem Unternehmensschnitt' : 'Im Unternehmensschnitt'}
						{:else}Gesamtbild deines Teams{/if}
					</p>
					<ul class="mt-2 flex flex-col gap-1 text-sm" style="color: var(--text-secondary)">
						{#if overall != null && overallPrev != null}
							<li>{overall >= overallPrev ? '▲' : '▼'} <b style="color: {overall >= overallPrev ? 'var(--success)' : 'var(--danger)'}">{signed(overall - overallPrev)}</b> zur Vorrunde</li>
						{/if}
						{#if overall != null && overallCompany != null}
							<li>{overall >= overallCompany ? '▲' : '▼'} <b>{signed(overall - overallCompany)}</b> zum Unternehmen (Ø {fmt(overallCompany)})</li>
						{/if}
						<li>👥 {detail.n_responses} Antworten</li>
					</ul>
				</div>
			</div>

			<!-- Stärken / Entwicklungsfelder -->
			<div class="mb-4 grid gap-3 md:grid-cols-2">
				<div class="glass-surface p-4">
					<p class="mb-2 font-semibold" style="color: var(--success)">▲ Das läuft gut</p>
					{#each strengths as d (d.dimension)}
						<button class="row" onclick={() => { tab = 'themen'; openDim = d.dimension; }}>
							<span>{d.dimension}</span><b>{fmt(d.mean)}</b>
						</button>
					{/each}
				</div>
				<div class="glass-surface p-4">
					<p class="mb-2 font-semibold" style="color: var(--danger)">▼ Hier steckt Potenzial</p>
					{#each growth as d (d.dimension)}
						<button class="row" onclick={() => { tab = 'themen'; openDim = d.dimension; }}>
							<span>{d.dimension}</span><b>{fmt(d.mean)}</b>
						</button>
					{/each}
					<a href="/massnahmen" class="mt-2 inline-block text-sm" style="color: var(--accent-text)">→ Maßnahme daraus ableiten</a>
				</div>
			</div>

			<!-- NPS -->
			{#if detail.nps && detail.nps.n > 0}
				<div class="glass-surface mb-4 p-4">
					<div class="mb-2 flex items-baseline justify-between">
						<p class="font-semibold" style="color: var(--text-primary)">Würde dich das Team weiterempfehlen?</p>
						<p class="text-2xl font-bold" style="color: var(--text-primary)">NPS {detail.nps.score}</p>
					</div>
					<div class="flex h-4 overflow-hidden rounded-full" role="img" aria-label="Kritiker, Neutrale, Fans">
						<div style="width:{(detail.nps.detractors / detail.nps.n) * 100}%; background: var(--danger)"></div>
						<div style="width:{(detail.nps.passives / detail.nps.n) * 100}%; background: var(--warning)"></div>
						<div style="width:{(detail.nps.promoters / detail.nps.n) * 100}%; background: var(--success)"></div>
					</div>
					<p class="mt-2 text-xs" style="color: var(--text-secondary)">
						{detail.nps.detractors} Kritiker · {detail.nps.passives} Neutrale · {detail.nps.promoters} Fans
						{#if detail.nps_reference?.value != null && detail.nps.score != null}
							· Referenz „{detail.nps_reference.label}“: {detail.nps_reference.value}
						{/if}
					</p>
				</div>
			{/if}

			<!-- Auswahlfragen -->
			{#each (detail.questions ?? []).filter((q) => q.type === 'choice') as q (q.question)}
				<div class="glass-surface mb-4 p-4">
					<p class="mb-2 font-semibold" style="color: var(--text-primary)">{q.question}</p>
					{#each Object.entries(q.distribution) as [opt, cnt] (opt)}
						<div class="mb-1 flex items-center gap-2 text-sm" style="color: var(--text-secondary)">
							<span class="w-32 shrink-0 sm:w-48">{opt}</span>
							<div class="h-2.5 flex-1 rounded-full" style="background: var(--border-subtle)"><div class="h-2.5 rounded-full" style="width:{(cnt / q.n) * 100}%; background: var(--accent)"></div></div>
							<span class="w-8 text-right">{cnt}</span>
						</div>
					{/each}
				</div>
			{/each}

			<details class="text-sm" style="color: var(--text-secondary)">
				<summary class="cursor-pointer py-2">Wie lese ich den Report?</summary>
				<p class="pb-2">Die Werte gehen von 1 (trifft gar nicht zu) bis 5 (trifft voll zu) und sind Durchschnitte aller Antworten. Grün/Gelb/Rot zeigt den Abstand zum Unternehmensschnitt (± 0,2). Kleine Gruppen werden zum Schutz der Anonymität nicht angezeigt.</p>
			</details>
		{:else if tab === 'themen'}
			<p class="mb-3 text-sm" style="color: var(--text-secondary)">Tippe auf ein Thema für Details. Der Strich zeigt den Unternehmensschnitt, der Punkt die Vorrunde.</p>
			<div class="flex flex-col gap-3">
				{#each sorted as d (d.dimension)}
					{@const v = verdict(d)}
					<div class="glass-surface overflow-hidden">
						<button class="dim" aria-expanded={openDim === d.dimension} onclick={() => (openDim = openDim === d.dimension ? null : d.dimension)}>
							<div class="flex items-center justify-between gap-3">
								<span class="font-semibold" style="color: var(--text-primary)">{d.dimension}</span>
								<span class="text-2xl font-bold" style="color: var(--text-primary)">{fmt(d.mean)}</span>
							</div>
							<div class="bar" role="img" aria-label="{d.dimension}: {fmt(d.mean)} von 5">
								<div class="fill" style="width:{pct(d.mean)}; background: {v.color}"></div>
								{#if d.unternehmen}<div class="mark" style="left:{pct(d.unternehmen.mean)}" title="Unternehmen {fmt(d.unternehmen.mean)}"></div>{/if}
								{#if d.vorrunde}<div class="dot" style="left:{pct(d.vorrunde.mean)}" title="Vorrunde {fmt(d.vorrunde.mean)}"></div>{/if}
							</div>
							<div class="flex justify-between text-xs" style="color: var(--text-secondary)">
								<span style="color: {v.color}">● {v.label}{v.text ? ` (${v.text})` : ''}</span>
								{#if d.vorrunde}<span>{d.vorrunde.delta >= 0 ? '▲' : '▼'} {signed(d.vorrunde.delta)} zur Vorrunde</span>{/if}
							</div>
						</button>
						{#if openDim === d.dimension}
							<div class="border-t p-4 text-sm" style="border-color: var(--border-subtle); color: var(--text-secondary)">
								<div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
									{#each [['Ich', d.mean], ['Fachbereich', d.fachbereich?.mean], ['Unternehmen', d.unternehmen?.mean], ['Vorrunde', d.vorrunde?.mean]] as [l, val]}
										<div class="rounded-[var(--radius-sm)] p-2 text-center" style="background: var(--surface-glass-strong)"><div class="text-lg font-bold" style="color: var(--text-primary)">{fmt(val as number | null)}</div><div class="text-xs">{l}</div></div>
									{/each}
								</div>
								<p class="mt-3 mb-1 text-xs">Wie haben die {d.n} Personen geantwortet?</p>
								<div class="flex items-end gap-2" aria-label="Verteilung der Antworten">
									{#each Object.entries(d.distribution) as [k, cnt] (k)}
										<div class="flex-1 text-center text-xs">
											<div class="mx-auto w-full max-w-10 rounded-t" style="height:{Math.max(4, (cnt / maxCount(d.distribution)) * 56)}px; background: var(--accent); opacity:.7"></div>
											{k}<br /><span style="color: var(--text-muted)">{cnt}×</span>
										</div>
									{/each}
								</div>
								<p class="mt-2 text-xs" style="color: var(--text-muted)">Median {d.median} · Streuung {d.stddev}</p>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{:else if tab === 'freitext'}
			{#if detail.ai_summary}
				<div class="glass-surface mb-4 p-4">
					<p class="mb-1 font-semibold" style="color: var(--text-primary)">✨ Kurz zusammengefasst</p>
					<p class="text-sm whitespace-pre-line" style="color: var(--text-secondary)">{detail.ai_summary}</p>
				</div>
			{/if}
			<div class="glass-surface p-4">
				<div class="seg mb-3">
					{#each [['kategorien', 'Themen'], ['wordcloud', 'Wörter'], ['alle', 'Alle Antworten']] as [id, label] (id)}
						<button class:on={textTab === id} onclick={() => (textTab = id as typeof textTab)}>{label}</button>
					{/each}
				</div>
				{#if textTab === 'kategorien'}
					{#each detail.categories ?? [] as c (c.category)}
						<details class="mb-2" open>
							<summary class="cursor-pointer py-1 font-semibold" style="color: var(--text-primary)">{c.category} <span class="text-xs font-normal" style="color: var(--text-muted)">({c.count})</span></summary>
							<ul class="ml-5 list-disc text-sm" style="color: var(--text-secondary)">{#each c.texts as t}<li class="py-0.5">{t}</li>{/each}</ul>
						</details>
					{:else}
						<p class="text-sm" style="color: var(--text-secondary)">Zu wenige Antworten je Thema, um sie anzuzeigen.</p>
					{/each}
				{:else if textTab === 'wordcloud'}
					<div class="flex flex-wrap items-center gap-x-4 gap-y-1" role="img" aria-label="Wörter aus den Freitexten">
						{#each detail.wordcloud ?? [] as w (w.word)}
							{@const max = detail.wordcloud?.[0].count ?? 1}
							<span style="font-size:{cloudSize(w.count, max)}rem; color: var(--accent-text); opacity:{0.55 + (w.count / max) * 0.45}" title="{w.count} Antworten">{w.word}</span>
						{:else}
							<p class="text-sm" style="color: var(--text-secondary)">Noch keine Wörter, die in mindestens 3 verschiedenen Antworten vorkommen.</p>
						{/each}
					</div>
				{:else}
					{#each detail.freetext ?? [] as g (g.question)}
						<p class="mt-2 text-sm font-semibold" style="color: var(--text-primary)">{g.question}</p>
						<ul class="ml-5 list-disc text-sm" style="color: var(--text-secondary)">{#each g.texts as t}<li class="py-0.5">{t}</li>{/each}</ul>
					{/each}
				{/if}
				<p class="mt-3 text-xs" style="color: var(--text-muted)">Freitexte sind von Namen und Kontaktdaten bereinigt und in zufälliger Reihenfolge – nicht rückverfolgbar.</p>
			</div>
		{:else}
			<div class="glass-surface p-4">
				{#if trendRounds.length < 2}
					<p class="text-sm" style="color: var(--text-secondary)">Ein Verlauf entsteht, sobald mindestens zwei Runden ausgewertet sind.</p>
				{:else}
					<svg viewBox="0 0 600 220" class="w-full" role="img" aria-label="Verlauf der Themen über die Runden" style="color: var(--text-secondary)">
						{#each [1, 2, 3, 4, 5] as g}
							<line x1="40" x2="580" y1={y(g)} y2={y(g)} stroke="currentColor" opacity=".15" />
							<text x="10" y={y(g) + 4} font-size="10" fill="currentColor">{g}</text>
						{/each}
						{#each trendRounds as r, i}<text x={x(i)} y="212" font-size="9" text-anchor="middle" fill="currentColor">{r}</text>{/each}
						{#each Object.entries(trend) as [name, pts], si (name)}
							<polyline fill="none" stroke={colors[si % 5]} stroke-width="2.5" points={pts.map((p) => `${x(trendRounds.indexOf(p.round))},${y(p.mean)}`).join(' ')} />
						{/each}
					</svg>
					<div class="mt-2 flex flex-wrap gap-3 text-xs" style="color: var(--text-secondary)">
						{#each Object.keys(trend) as name, si (name)}<span><span style="color:{colors[si % 5]}">■</span> {name}</span>{/each}
					</div>
				{/if}
			</div>
		{/if}
	{/if}
{/if}

<style>
	.btn {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		padding: 0 1.1rem;
		border-radius: var(--radius-sm);
		background: var(--accent);
		color: var(--accent-contrast);
		font-size: 0.875rem;
		font-weight: 600;
	}
	.btn.ghost {
		background: var(--surface-glass-strong);
		color: var(--text-primary);
		border: 1px solid var(--border-subtle);
	}
	.chip {
		flex: 0 0 auto;
		min-height: 40px;
		padding: 0 1rem;
		border-radius: 999px;
		font-size: 0.875rem;
		background: var(--surface-glass-strong);
		color: var(--text-primary);
	}
	.chip.on {
		background: var(--accent);
		color: var(--accent-contrast);
	}
	.seg {
		display: flex;
		gap: 0.25rem;
		padding: 0.25rem;
		border-radius: 999px;
		background: var(--surface-glass-strong);
		border: 1px solid var(--border-subtle);
		overflow-x: auto;
	}
	.seg button {
		flex: 1 0 auto;
		min-height: 40px;
		padding: 0 1rem;
		border-radius: 999px;
		font-size: 0.875rem;
		color: var(--text-secondary);
	}
	.seg button.on {
		background: var(--accent);
		color: var(--accent-contrast);
		font-weight: 600;
	}
	.hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1.25rem;
	}
	@media (min-width: 640px) {
		.hero {
			flex-direction: row;
		}
	}
	.row {
		display: flex;
		width: 100%;
		justify-content: space-between;
		min-height: 44px;
		align-items: center;
		border-radius: var(--radius-sm);
		padding: 0 0.6rem;
		color: var(--text-primary);
		text-align: left;
	}
	.row:hover {
		background: var(--surface-glass-strong);
	}
	.dim {
		display: flex;
		width: 100%;
		flex-direction: column;
		gap: 0.6rem;
		padding: 1rem;
		text-align: left;
	}
	.bar {
		position: relative;
		height: 12px;
		border-radius: 999px;
		background: var(--border-subtle);
	}
	.fill {
		height: 12px;
		border-radius: 999px;
	}
	.mark {
		position: absolute;
		top: -4px;
		width: 3px;
		height: 20px;
		border-radius: 2px;
		background: var(--text-primary);
	}
	.dot {
		position: absolute;
		top: 1px;
		width: 10px;
		height: 10px;
		margin-left: -5px;
		border-radius: 999px;
		background: var(--surface-glass-strong);
		border: 2px solid var(--text-secondary);
	}
</style>
