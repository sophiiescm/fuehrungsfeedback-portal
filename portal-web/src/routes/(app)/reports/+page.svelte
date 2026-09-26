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
	interface Detail {
		available: boolean;
		message?: string;
		round_name: string;
		n_responses: number;
		dimensions?: Dim[];
		questions?: { question: string; mean: number; n: number }[];
		freetext?: string[];
		ai_summary?: string | null;
	}
	let list = $state<{ target_id: number; round_name: string }[]>([]);
	let detail = $state<Detail | null>(null);
	let selected = $state<number | null>(null);
	let trend = $state<Record<string, { round: string; mean: number }[]>>({});

	onMount(async () => {
		list = await api.get('/reports/mine');
		trend = (await api.get<{ series: typeof trend }>('/reports/mine/trend')).series;
		if (list.length) open(list[0].target_id);
	});
	async function open(id: number) {
		selected = id;
		detail = await api.get<Detail>(`/reports/${id}`);
	}

	const colors = ['#4f46e5', '#0891b2', '#16a34a', '#d97706', '#dc2626'];
	const rounds = $derived([...new Set(Object.values(trend).flatMap((s) => s.map((p) => p.round)))]);
	const x = (i: number) => 40 + (rounds.length > 1 ? (i * 520) / (rounds.length - 1) : 260);
	const y = (v: number) => 180 - ((v - 1) / 4) * 160;
</script>

<h1 class="mb-6 text-2xl font-bold" style="color: var(--text-primary)">Meine Reports / Trend</h1>

{#if list.length === 0}
	<Card><p style="color: var(--text-secondary)">Noch kein Report verfügbar.</p></Card>
{/if}

<div class="mb-4 flex flex-wrap gap-2">
	{#each list as r (r.target_id)}
		<button
			onclick={() => open(r.target_id)}
			class="rounded-[var(--radius-sm)] px-3 py-2 text-sm"
			style="background: {selected === r.target_id ? 'var(--accent)' : 'var(--surface-glass)'}; color: {selected === r.target_id ? 'var(--accent-contrast)' : 'var(--text-primary)'}"
		>{r.round_name}</button>
	{/each}
</div>

{#if detail}
	{#if !detail.available}
		<Card title="Kein Report"><p style="color: var(--text-primary)">{detail.message}</p></Card>
	{:else}
		<Card title={`${detail.round_name} · ${detail.n_responses} Antworten`}>
			<div class="flex flex-col gap-3">
				{#each detail.dimensions ?? [] as d (d.dimension)}
					<div>
						<div class="flex justify-between text-sm" style="color: var(--text-primary)">
							<span>{d.dimension}</span>
							<span>Ø {d.mean.toFixed(2)} · Median {d.median} · σ {d.stddev} · {d.min}–{d.max}</span>
						</div>
						<div class="relative h-3 rounded" style="background: var(--border-subtle)" role="img" aria-label={`${d.dimension} Mittelwert ${d.mean}`}>
							<div class="h-3 rounded" style="width:{(d.mean / 5) * 100}%; background: var(--accent)"></div>
							{#if d.fachbereich}<div class="absolute top-0 h-3 w-0.5" style="left:{(d.fachbereich.mean / 5) * 100}%; background: var(--warning)" title="Fachbereich"></div>{/if}
							{#if d.unternehmen}<div class="absolute top-0 h-3 w-0.5" style="left:{(d.unternehmen.mean / 5) * 100}%; background: var(--success)" title="Unternehmen"></div>{/if}
						</div>
						<div class="mt-1 flex flex-wrap gap-3 text-xs" style="color: var(--text-secondary)">
							<span>Fachbereich: {d.fachbereich ? d.fachbereich.mean.toFixed(2) : '–'}</span>
							<span>Unternehmen: {d.unternehmen ? d.unternehmen.mean.toFixed(2) : '–'}</span>
							<span>Vorrunde: {d.vorrunde ? `${d.vorrunde.mean.toFixed(2)} (${d.vorrunde.delta >= 0 ? '+' : ''}${d.vorrunde.delta.toFixed(2)})` : '–'}</span>
						</div>
						<div class="mt-1 flex items-end gap-1" aria-label="Verteilung">
							{#each Object.entries(d.distribution) as [k, v] (k)}
								<div class="text-center text-[10px]" style="color: var(--text-muted)">
									<div style="height:{Math.max(2, (v / d.n) * 40)}px; width:14px; background: var(--accent); opacity:.6"></div>{k}
								</div>
							{/each}
						</div>
					</div>
				{/each}
			</div>
			<div class="mt-4">
				<Button variant="secondary" onclick={() => downloadPdf(`/reports/${selected}/pdf`, 'report.pdf')}>Als PDF herunterladen</Button>
			</div>
		</Card>

		{#if detail.ai_summary}<div class="mt-4"><Card title="Zusammenfassung der Freitexte (KI)"><p class="text-sm whitespace-pre-line" style="color: var(--text-primary)">{detail.ai_summary}</p></Card></div>{/if}
		{#if detail.freetext?.length}
			<div class="mt-4">
				<Card title="Freitext-Rückmeldungen (geschwärzt, zufällige Reihenfolge)">
					<ul class="list-inside list-disc text-sm" style="color: var(--text-primary)">
						{#each detail.freetext as t}<li>{t}</li>{/each}
					</ul>
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
