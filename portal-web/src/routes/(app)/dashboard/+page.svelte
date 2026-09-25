<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';
	import Card from '$lib/components/Card.svelte';
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
		<p style="color: var(--text-secondary)">Alles erledigt.</p>
	</Card>
</div>
