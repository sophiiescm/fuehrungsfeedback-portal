<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth.svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import { api, ApiError } from '$lib/api/client';

	interface Action {
		id: number;
		title: string;
		description: string | null;
		topic: string | null;
		status: 'geplant' | 'in_arbeit' | 'erledigt';
		due_date: string | null;
		visible_to_team: boolean;
		round_id: number | null;
	}
	interface Suggestion { topic: string; mean: number; title: string; round_id: number }

	const STATUS = { geplant: 'Geplant', in_arbeit: 'In Arbeit', erledigt: 'Erledigt' } as const;
	const NEXT = { geplant: 'in_arbeit', in_arbeit: 'erledigt', erledigt: 'geplant' } as const;

	let mine = $state<Action[]>([]);
	let team = $state<{ leader: string | null; actions: Action[] }>({ leader: null, actions: [] });
	let suggestions = $state<Suggestion[]>([]);
	let title = $state('');
	let description = $state('');
	let topic = $state<string | null>(null);
	let dueDate = $state('');
	let visible = $state(true);
	let error = $state('');

	const isLeader = $derived(auth.hasRole('fuehrungskraft'));

	async function load() {
		team = await api.get('/actions/team');
		if (isLeader) {
			mine = await api.get('/actions/mine');
			suggestions = await api.get('/actions/suggestions');
		}
	}
	onMount(load);

	async function add(preset?: Suggestion) {
		error = '';
		try {
			await api.post('/actions', {
				title: preset?.title ?? title.trim(),
				topic: preset?.topic ?? topic,
				round_id: preset?.round_id ?? null,
				description: description.trim() || null,
				due_date: dueDate || null,
				visible_to_team: visible
			});
			title = description = dueDate = '';
			topic = null;
			await load();
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Konnte nicht gespeichert werden';
		}
	}
	async function put(a: Action, patch: Partial<Action>) {
		const b = { ...a, ...patch };
		await api.put(`/actions/${a.id}`, b);
		await load();
	}
	async function remove(a: Action) {
		await api.delete(`/actions/${a.id}`);
		await load();
	}
</script>

<h1 class="mb-1 text-2xl font-bold" style="color: var(--text-primary)">Maßnahmen</h1>
<p class="mb-5 text-sm" style="color: var(--text-secondary)">Feedback wirkt, wenn daraus etwas folgt. Hier siehst du, was sich getan hat.</p>

{#if team.leader}
	<Card title={`Das tut ${team.leader} für dein Team`}>
		{#if team.actions.length === 0}
			<p class="text-sm" style="color: var(--text-secondary)">Noch keine veröffentlichten Maßnahmen.</p>
		{/if}
		<ul class="flex flex-col gap-2">
			{#each team.actions as a (a.id)}
				<li class="item">
					<span class="badge {a.status}">{STATUS[a.status]}</span>
					<div><p style="color: var(--text-primary)">{a.title}</p>{#if a.description}<p class="text-sm" style="color: var(--text-secondary)">{a.description}</p>{/if}
						{#if a.due_date}<p class="text-xs" style="color: var(--text-muted)">bis {a.due_date}</p>{/if}</div>
				</li>
			{/each}
		</ul>
	</Card>
{/if}

{#if isLeader}
	<div class="mt-4 flex flex-col gap-4">
		{#if suggestions.length}
			<Card title="Vorschläge aus deinem Report">
				<p class="mb-3 text-sm" style="color: var(--text-secondary)">Die drei Themen mit dem größten Entwicklungspotenzial:</p>
				<ul class="flex flex-col gap-2">
					{#each suggestions as s (s.topic)}
						<li class="item"><div class="flex-1"><p style="color: var(--text-primary)">{s.title}</p><p class="text-xs" style="color: var(--text-muted)">Ø {s.mean.toFixed(2)}</p></div>
							<Button variant="secondary" onclick={() => add(s)}>Übernehmen</Button></li>
					{/each}
				</ul>
			</Card>
		{/if}

		<Card title="Meine Maßnahmen">
			<ul class="mb-4 flex flex-col gap-2">
				{#each mine as a (a.id)}
					<li class="item">
						<button class="badge {a.status}" onclick={() => put(a, { status: NEXT[a.status] })} title="Status ändern">{STATUS[a.status]}</button>
						<div class="flex-1">
							<p style="color: var(--text-primary)">{a.title}</p>
							<p class="text-xs" style="color: var(--text-muted)">{a.topic ?? ''}{a.due_date ? ` · bis ${a.due_date}` : ''} · {a.visible_to_team ? 'für Team sichtbar' : 'nur für mich'}</p>
						</div>
						<button class="text-xs" style="color: var(--text-secondary)" onclick={() => put(a, { visible_to_team: !a.visible_to_team })}>{a.visible_to_team ? 'Verbergen' : 'Teilen'}</button>
						<button class="text-xs" style="color: var(--danger)" onclick={() => remove(a)}>Löschen</button>
					</li>
				{/each}
				{#if mine.length === 0}<li class="text-sm" style="color: var(--text-secondary)">Noch keine Maßnahmen angelegt.</li>{/if}
			</ul>
			<div class="flex flex-col gap-2">
				<input placeholder="Neue Maßnahme, z. B. „Jeden Montag 15 Min. Team-Austausch“" bind:value={title} class="glass-surface rounded-[var(--radius-sm)] px-3 py-2" style="color: var(--text-primary)" />
				<textarea placeholder="Details (optional)" bind:value={description} class="glass-surface rounded-[var(--radius-sm)] px-3 py-2" style="color: var(--text-primary)"></textarea>
				<div class="flex flex-wrap items-center gap-3 text-sm" style="color: var(--text-secondary)">
					<label>Bis <input type="date" bind:value={dueDate} class="glass-surface rounded px-2 py-1" /></label>
					<label class="flex items-center gap-2"><input type="checkbox" bind:checked={visible} /> Team darf es sehen</label>
				</div>
				{#if error}<p class="text-sm" style="color: var(--danger)">{error}</p>{/if}
				<div><Button onclick={() => add()} disabled={title.trim().length < 3}>Maßnahme hinzufügen</Button></div>
			</div>
		</Card>
	</div>
{:else if !team.leader}
	<Card><p class="text-sm" style="color: var(--text-secondary)">Hier erscheinen Maßnahmen, sobald deine Führungskraft welche veröffentlicht.</p></Card>
{/if}

<style>
	.item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: var(--surface-glass-strong);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-md);
		padding: 0.7rem 0.9rem;
	}
	.badge {
		flex: 0 0 auto;
		border-radius: 999px;
		padding: 0.25rem 0.7rem;
		font-size: 0.75rem;
		font-weight: 600;
		min-height: 32px;
		color: #fff;
	}
	.badge.geplant { background: var(--text-muted); }
	.badge.in_arbeit { background: var(--warning); }
	.badge.erledigt { background: var(--success); }
</style>
