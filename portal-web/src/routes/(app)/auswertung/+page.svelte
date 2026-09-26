<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import { api } from '$lib/api/client';
	import { roundsApi, type Round } from '$lib/api/rounds';

	type Bench = Record<
		string,
		{ suppressed: boolean; leaders?: { pseudonym: string; dimensions: Record<string, number> }[] | number; mean_by_dimension?: Record<string, number> }
	>;
	let rounds = $state<Round[]>([]);
	let roundId = $state<number | null>(null);
	let fachbereich = $state('');
	let bench = $state<Bench>({});
	let msg = $state('');

	onMount(async () => {
		rounds = await roundsApi.list();
		roundId = rounds.find((r) => r.status === 'berichtet' || r.status === 'ausgewertet')?.id ?? rounds[0]?.id ?? null;
		if (roundId) await load();
	});
	async function load() {
		if (!roundId) return;
		bench = await api.get<Bench>(`/benchmark?round_id=${roundId}${fachbereich ? `&fachbereich=${encodeURIComponent(fachbereich)}` : ''}`);
	}
	async function act(kind: 'evaluate' | 'distribute') {
		try {
			msg = JSON.stringify(await api.post(`/rounds/${roundId}/${kind}`));
			rounds = await roundsApi.list();
		} catch (e) {
			msg = e instanceof Error ? e.message : 'Fehler';
		}
	}
	const current = $derived(rounds.find((r) => r.id === roundId));
</script>

<h1 class="mb-6 text-2xl font-bold" style="color: var(--text-primary)">Auswertung & Benchmarking</h1>

<Card title="Runde">
	<div class="flex flex-wrap items-center gap-2">
		<select bind:value={roundId} onchange={load} class="glass-surface rounded px-3 py-2 text-sm" style="color: var(--text-primary)">
			{#each rounds as r (r.id)}<option value={r.id}>{r.name} ({r.status})</option>{/each}
		</select>
		<input placeholder="Fachbereich (optional)" bind:value={fachbereich} class="glass-surface rounded px-3 py-2 text-sm" style="color: var(--text-primary)" />
		<Button variant="secondary" onclick={load}>Filtern</Button>
		{#if current?.status === 'geschlossen'}<Button onclick={() => act('evaluate')}>Auswerten</Button>{/if}
		{#if current?.status === 'ausgewertet'}<Button onclick={() => act('distribute')}>Reports verteilen</Button>{/if}
	</div>
	{#if msg}<p class="mt-2 text-xs" style="color: var(--text-secondary)">{msg}</p>{/if}
</Card>

<div class="mt-4 flex flex-col gap-4">
	{#each Object.entries(bench) as [name, g] (name)}
		<Card title={name === '_gesamt' ? 'Gesamtunternehmen' : name}>
			{#if g.suppressed}
				<p class="text-sm" style="color: var(--text-secondary)">Unterdrückt: weniger als 3 Führungskräfte (Anonymitätsschwelle).</p>
			{:else if g.mean_by_dimension}
				<p class="text-sm" style="color: var(--text-primary)">{g.leaders} Führungskräfte</p>
				{#each Object.entries(g.mean_by_dimension) as [dim, v] (dim)}
					<div class="text-sm" style="color: var(--text-secondary)">{dim}: Ø {v}</div>
				{/each}
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
