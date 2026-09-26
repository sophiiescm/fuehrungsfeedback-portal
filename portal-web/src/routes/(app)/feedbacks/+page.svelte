<script lang="ts">
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import { feedbackApi, type MyFeedback } from '$lib/api/rounds';

	let items = $state<MyFeedback[]>([]);
	let loaded = $state(false);
	onMount(async () => {
		items = await feedbackApi.mine();
		loaded = true;
	});
	const open = $derived(items.filter((i) => i.status === 'offen'));
	const done = $derived(items.filter((i) => i.status === 'erledigt'));
</script>

<h1 class="mb-6 text-2xl font-bold" style="color: var(--text-primary)">Meine Feedbacks</h1>

<Card>
	<p class="text-lg" style="color: var(--text-primary)" data-testid="open-summary">
		{#if !loaded}Lädt…{:else if open.length === 0}Alles erledigt.{:else}Du hast {open.length} offene{open.length === 1 ? 's Feedback' : ' Feedbacks'}.{/if}
	</p>
</Card>

<div class="mt-4 flex flex-col gap-3">
	{#each open as f (f.participation_id)}
		<Card>
			<div class="flex flex-wrap items-center justify-between gap-2">
				<div>
					<p style="color: var(--text-primary)">{f.round_name}: Feedback für {f.leader_name}</p>
					<p class="text-sm" style="color: var(--text-secondary)">Fällig bis {f.due_date}</p>
				</div>
				{#if f.feedback_link}
					<a href={f.feedback_link} class="rounded-[var(--radius-sm)] px-4 py-2 text-sm" style="background: var(--accent); color: var(--accent-contrast)">Jetzt Feedback geben</a>
				{/if}
			</div>
		</Card>
	{/each}
	{#each done as f (f.participation_id)}
		<Card>
			<p style="color: var(--text-primary)">✓ {f.round_name}: Feedback für {f.leader_name}</p>
			<p class="text-sm" style="color: var(--text-secondary)">Abgegeben am {f.completed_date}</p>
		</Card>
	{/each}
</div>

<Card title="Hinweis zu deinen Antworten">
	<p class="text-sm" style="color: var(--text-secondary)">
		Die Befragung ist anonym: Das Portal speichert nur, <em>dass</em> du teilgenommen hast, nie <em>was</em> du geantwortet hast.
		Deshalb kannst du deine Antworten später nicht mehr einsehen. Direkt nach dem Absenden kannst du sie
		über „Antworten drucken / als PDF speichern“ auf der Abschlussseite sichern.
	</p>
</Card>
