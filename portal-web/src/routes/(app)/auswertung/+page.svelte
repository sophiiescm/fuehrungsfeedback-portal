<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import { api } from '$lib/api/client';
	import { roundsApi, downloadFile, type Round } from '$lib/api/rounds';
	import { organisationApi } from '$lib/api/organisation';

	interface Nps { score: number | null; n: number; promoters: number; passives: number; detractors: number; leaders: number }
	interface Cell { mean: number; delta: number | null; ampel: 'gruen' | 'gelb' | 'rot' | null }
	interface Compare {
		dimensions: string[];
		company: Record<string, number | null>;
		groups: Record<string, { suppressed: boolean; leaders: number; dimensions: Record<string, Cell | null>; nps: Nps | null }>;
		company_nps: Nps | null;
		nps_reference: { value: number | null; label: string } | null;
	}
	type Bench = Record<string, { suppressed: boolean; leaders?: { pseudonym: string; dimensions: Record<string, number> }[] | number; mean_by_dimension?: Record<string, number> }>;

	let tab = $state<'vergleich' | 'nps' | 'fk'>('vergleich');
	let view = $state<'balken' | 'ampel'>('balken');
	let rounds = $state<Round[]>([]);
	let roundId = $state<number | null>(null);
	let fachbereiche = $state<string[]>([]);
	let selected = $state<string[]>([]);
	let cmp = $state<Compare | null>(null);
	let bench = $state<Bench>({});
	let msg = $state('');
	let refValue = $state('');
	let refLabel = $state('');

	onMount(async () => {
		rounds = await roundsApi.list();
		fachbereiche = await organisationApi.listFachbereiche();
		roundId = rounds.find((r) => r.status === 'berichtet' || r.status === 'ausgewertet')?.id ?? rounds[0]?.id ?? null;
		const ref = await api.get<{ value: number | null; label: string }>('/nps/reference');
		refValue = ref.value?.toString() ?? '';
		refLabel = ref.label ?? '';
		if (roundId) {
			const b = await api.get<Bench>(`/benchmark?round_id=${roundId}`);
			const usable = fachbereiche.filter((f) => b[f] && !b[f].suppressed);
			selected = (usable.length ? usable : fachbereiche).slice(0, 2);
		}
		await load();
	});

	async function load() {
		if (!roundId) return;
		if (selected.length) {
			cmp = await api.get<Compare>(`/benchmark/compare?round_id=${roundId}&groups=${encodeURIComponent(selected.join(','))}`);
		} else {
			cmp = null;
		}
		bench = await api.get<Bench>(`/benchmark?round_id=${roundId}`);
	}
	function toggle(f: string) {
		selected = selected.includes(f) ? selected.filter((x) => x !== f) : [...selected, f];
		load();
	}
	async function act(kind: 'evaluate' | 'distribute') {
		try {
			msg = JSON.stringify(await api.post(`/rounds/${roundId}/${kind}`));
			rounds = await roundsApi.list();
			await load();
		} catch (e) {
			msg = e instanceof Error ? e.message : 'Fehler';
		}
	}
	async function saveRef() {
		await api.put('/nps/reference', { value: Number(refValue), label: refLabel });
		await load();
	}
	const current = $derived(rounds.find((r) => r.id === roundId));
	const colors = ['#004f23', '#007298', '#d97706', '#16a34a', '#dc2626', '#7c3aed'];
	const ampelColor = { gruen: 'var(--success)', gelb: 'var(--warning)', rot: 'var(--danger)' } as const;
	const pct = (v: number) => `${(v / 5) * 100}%`;
	const ref = $derived(cmp?.nps_reference?.value ?? null);
	const npsRows = $derived<[string, Nps | null][]>([
		['Unternehmen', cmp?.company_nps ?? null],
		...Object.entries(cmp?.groups ?? {}).map(([n, g]) => [n, g.nps] as [string, Nps | null])
	]);
</script>

<h1 class="mb-6 text-2xl font-bold" style="color: var(--text-primary)">Auswertung & Benchmarking</h1>

<Card title="Vergleichsgruppen wählen">
	<div class="mb-3 flex flex-wrap items-center gap-2">
		<select bind:value={roundId} onchange={load} class="glass-surface rounded px-3 py-2 text-sm" style="color: var(--text-primary)" aria-label="Runde">
			{#each rounds as r (r.id)}<option value={r.id}>{r.name} ({r.status})</option>{/each}
		</select>
		{#if roundId}
			{#each [['xlsx', 'Excel'], ['pptx', 'PowerPoint'], ['csv', 'CSV']] as [f, l] (f)}
				<Button variant="secondary" onclick={() => downloadFile(`/benchmark/export.${f}?round_id=${roundId}`, `benchmark-${roundId}.${f}`).catch((e) => (msg = e.message))}>⬇ {l}</Button>
			{/each}
		{/if}
		{#if current?.status === 'geschlossen'}<Button onclick={() => act('evaluate')}>Auswerten</Button>{/if}
		{#if current?.status === 'ausgewertet'}<Button onclick={() => act('distribute')}>Reports verteilen</Button>{/if}
	</div>
	<p class="mb-2 text-xs" style="color: var(--text-secondary)">Wer soll miteinander verglichen werden? (z. B. nur Vertrieb, oder IT vs. Vertrieb)</p>
	<div class="flex flex-wrap gap-2">
		{#each fachbereiche as f (f)}
			<button
				onclick={() => toggle(f)}
				aria-pressed={selected.includes(f)}
				class="rounded-full px-3 py-1 text-sm"
				style="background: {selected.includes(f) ? 'var(--accent)' : 'var(--surface-glass-strong)'}; color: {selected.includes(f) ? 'var(--accent-contrast)' : 'var(--text-primary)'}"
			>{f}</button>
		{/each}
	</div>
	{#if msg}<p class="mt-2 text-xs" style="color: var(--text-secondary)">{msg}</p>{/if}
</Card>

<div class="my-5 flex gap-2">
	{#each [['vergleich', 'Vergleich'], ['nps', 'NPS'], ['fk', 'Führungskräfte (pseudonymisiert)']] as [id, label] (id)}
		<button
			onclick={() => (tab = id as typeof tab)}
			class="rounded-full px-4 py-2 text-sm"
			style="background: {tab === id ? 'var(--accent)' : 'var(--surface-glass)'}; color: {tab === id ? 'var(--accent-contrast)' : 'var(--text-primary)'}"
		>{label}</button>
	{/each}
</div>

{#if tab === 'vergleich'}
	{#if !cmp}
		<Card><p style="color: var(--text-secondary)">Bitte mindestens eine Gruppe wählen.</p></Card>
	{:else}
		<div class="mb-3 flex gap-2 text-sm">
			{#each [['balken', 'Balken'], ['ampel', 'Werte + Ampel']] as [id, label] (id)}
				<button
					onclick={() => (view = id as typeof view)}
					class="rounded-full px-3 py-1"
					style="background: {view === id ? 'var(--accent)' : 'var(--surface-glass-strong)'}; color: {view === id ? 'var(--accent-contrast)' : 'var(--text-primary)'}"
				>{label}</button>
			{/each}
		</div>
		<Card>
			{#if view === 'balken'}
				<div class="flex flex-col gap-4">
					{#each cmp.dimensions as dim (dim)}
						<div>
							<p class="mb-1 text-sm font-semibold" style="color: var(--text-primary)">{dim}</p>
							{#each Object.entries(cmp.groups) as [name, g], gi (name)}
								<div class="mb-1 flex items-center gap-2 text-xs" style="color: var(--text-secondary)">
									<span class="w-28 shrink-0">{name}</span>
									<div class="relative h-3 flex-1 rounded" style="background: var(--border-subtle)">
										{#if g.dimensions[dim]}<div class="h-3 rounded" style="width:{pct(g.dimensions[dim]!.mean)}; background:{colors[gi % colors.length]}"></div>{/if}
										{#if cmp.company[dim] != null}<div class="absolute top-[-2px] h-4 w-0.5" style="left:{pct(cmp.company[dim]!)}; background: var(--text-primary)" title="Unternehmen"></div>{/if}
									</div>
									<span class="w-24 text-right">
										{#if g.dimensions[dim]}{g.dimensions[dim]!.mean.toFixed(2)}{:else}unterdrückt{/if}
									</span>
								</div>
							{/each}
						</div>
					{/each}
				</div>
				<p class="mt-3 text-xs" style="color: var(--text-muted)">Senkrechter Strich = Unternehmensmittel. Gruppen mit weniger als 3 Führungskräften werden unterdrückt.</p>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-left text-sm" style="color: var(--text-primary)">
						<thead>
							<tr>
								<th class="p-2">Dimension</th>
								<th class="p-2">Unternehmen</th>
								{#each Object.keys(cmp.groups) as name (name)}<th class="p-2">{name}</th>{/each}
							</tr>
						</thead>
						<tbody>
							{#each cmp.dimensions as dim (dim)}
								<tr class="border-t" style="border-color: var(--border-subtle)">
									<td class="p-2">{dim}</td>
									<td class="p-2">{cmp.company[dim]?.toFixed(2) ?? '–'}</td>
									{#each Object.values(cmp.groups) as g}
										{@const c = g.dimensions[dim]}
										<td class="p-2">
											{#if c}
												<span style="color:{c.ampel ? ampelColor[c.ampel] : 'inherit'}">●</span>
												{c.mean.toFixed(2)}
												<span class="text-xs" style="color: var(--text-muted)">({(c.delta ?? 0) >= 0 ? '+' : ''}{(c.delta ?? 0).toFixed(2)})</span>
											{:else}–{/if}
										</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<p class="mt-3 text-xs" style="color: var(--text-muted)">● grün ≥ +0,2 · gelb dazwischen · rot ≤ −0,2 gegenüber dem Unternehmensmittel.</p>
			{/if}
		</Card>
	{/if}
{:else if tab === 'nps'}
	<Card title="Net Promoter Score (NPS)">
		<div class="flex flex-col gap-3">
			{#each npsRows as [name, n] (name)}
				<div>
					<div class="flex justify-between text-sm" style="color: var(--text-primary)">
						<span>{name}</span>
						<span>{n ? `NPS ${n.score} (${n.leaders} FK, ${n.n} Antworten)` : 'unterdrückt / keine NPS-Frage'}</span>
					</div>
					{#if n && n.n > 0}
						<div class="mt-1 flex h-4 overflow-hidden rounded" role="img" aria-label="Detractors, Passive, Promoter">
							<div style="width:{(n.detractors / n.n) * 100}%; background: var(--danger)"></div>
							<div style="width:{(n.passives / n.n) * 100}%; background: var(--warning)"></div>
							<div style="width:{(n.promoters / n.n) * 100}%; background: var(--success)"></div>
						</div>
						{#if ref !== null && n.score !== null}
							<p class="text-xs" style="color: {n.score >= ref ? 'var(--success)' : 'var(--danger)'}">
								{n.score >= ref ? '▲' : '▼'} {Math.abs(n.score - ref).toFixed(1)} Punkte {n.score >= ref ? 'über' : 'unter'} Referenz „{cmp?.nps_reference?.label}“ ({ref})
							</p>
						{/if}
					{/if}
				</div>
			{/each}
		</div>
		<div class="mt-5 border-t pt-4" style="border-color: var(--border-subtle)">
			<p class="mb-2 text-sm font-semibold" style="color: var(--text-primary)">Externer Referenzwert (manuell)</p>
			<p class="mb-2 text-xs" style="color: var(--text-secondary)">
				Für den externen Vergleich (z. B. Branchen-NPS) hier einen Wert eintragen. Es wird keine externe Datenquelle angebunden.
			</p>
			<div class="flex flex-wrap gap-2">
				<input type="number" placeholder="NPS-Referenz" bind:value={refValue} class="glass-surface rounded px-3 py-2 text-sm" style="color: var(--text-primary)" />
				<input placeholder="Bezeichnung (z. B. Branche 2026)" bind:value={refLabel} class="glass-surface rounded px-3 py-2 text-sm" style="color: var(--text-primary)" />
				<Button variant="secondary" onclick={saveRef} disabled={refValue === ''}>Speichern</Button>
			</div>
		</div>
	</Card>
{:else}
	<div class="flex flex-col gap-4">
		{#each Object.entries(bench) as [name, g] (name)}
			<Card title={name === '_gesamt' ? 'Gesamtunternehmen' : name}>
				{#if g.suppressed}
					<p class="text-sm" style="color: var(--text-secondary)">Unterdrückt: weniger als 3 Führungskräfte (Anonymitätsschwelle).</p>
				{:else if g.mean_by_dimension}
					<p class="text-sm" style="color: var(--text-primary)">{g.leaders} Führungskräfte</p>
					{#each Object.entries(g.mean_by_dimension) as [dim, v] (dim)}<div class="text-sm" style="color: var(--text-secondary)">{dim}: Ø {v}</div>{/each}
				{:else if Array.isArray(g.leaders)}
					<div class="overflow-x-auto">
						<table class="w-full text-left text-xs" style="color: var(--text-primary)">
							<thead><tr><th class="p-1">Führungskraft</th>{#each Object.keys(g.leaders[0].dimensions) as d (d)}<th class="p-1">{d}</th>{/each}</tr></thead>
							<tbody>
								{#each g.leaders as l (l.pseudonym)}
									<tr><td class="p-1">{l.pseudonym}</td>{#each Object.values(l.dimensions) as v}<td class="p-1">{v.toFixed(2)}</td>{/each}</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</Card>
		{/each}
	</div>
{/if}
