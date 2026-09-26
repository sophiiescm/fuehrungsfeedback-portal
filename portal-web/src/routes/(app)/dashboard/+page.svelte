<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';
	import { onMount } from 'svelte';
	import Card from '$lib/components/Card.svelte';
	import { feedbackApi } from '$lib/api/rounds';

	let openCount = $state<number | null>(null);
	let dueDate = $state('');
	onMount(async () => {
		const items = await feedbackApi.mine();
		const open = items.filter((i) => i.status === 'offen');
		openCount = open.length;
		dueDate = open.map((i) => i.due_date).sort()[0] ?? '';
	});
</script>

<h1 class="mb-6 text-2xl font-bold" style="color: var(--text-primary)">Dashboard</h1>

<div class="grid gap-4 md:grid-cols-2">
	{#if auth.hasRole('admin')}
		<Card title="Gesamtstatus">
			<p style="color: var(--text-secondary)">
				Rücklaufquoten und Rundenübersicht folgen, sobald Befragungsrunden existieren (Phase 4).
			</p>
		</Card>
	{/if}
	{#if auth.hasRole('fuehrungskraft')}
		<Card title="Mein Report-Überblick">
			<p style="color: var(--text-secondary)">
				Reports erscheinen hier, sobald eine Runde ausgewertet wurde (Phase 5).
			</p>
		</Card>
	{/if}
	<Card title="Offene Aufgaben">
		<p style="color: var(--text-secondary)">
			{#if openCount === null}Lädt…{:else if openCount === 0}Alles erledigt.{:else}Du hast {openCount} offene{openCount === 1 ? 's Feedback' : ' Feedbacks'} (fällig bis {dueDate}).{/if}
		</p>
	</Card>
</div>
