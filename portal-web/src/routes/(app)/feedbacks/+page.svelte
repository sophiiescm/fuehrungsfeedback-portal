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
	const days = (iso: string) => Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000);
</script>

<h1 class="mb-1 text-2xl font-bold" style="color: var(--text-primary)">Meine Feedbacks</h1>
<p class="mb-5 text-sm" style="color: var(--text-secondary)" data-testid="open-summary">
	{#if !loaded}Lädt…{:else if open.length === 0}Alles erledigt.{:else}Du hast {open.length} offene{open.length === 1 ? 's Feedback' : ' Feedbacks'}.{/if}
</p>

<!-- Vertrauen zuerst: was passiert mit meinen Antworten? -->
<div class="trust mb-5" role="note">
	<strong>🔒 Dein Feedback ist anonym.</strong>
	<ul>
		<li>Niemand sieht, <em>was</em> du geantwortet hast. Das Portal merkt sich nur, <em>dass</em> du teilgenommen hast.</li>
		<li>Auswertungen gibt es erst ab 3 Antworten je Führungskraft – einzelne Personen sind nie erkennbar.</li>
		<li>Freitexte werden automatisch von Namen und Kontaktdaten bereinigt.</li>
	</ul>
</div>

<div class="flex flex-col gap-3">
	{#each open as f (f.participation_id)}
		<div class="glass-surface fb-card p-4 sm:p-5">
			<div>
				<p class="text-xs font-semibold tracking-wide uppercase" style="color: var(--accent)">{f.round_name}</p>
				<p class="text-lg font-semibold" style="color: var(--text-primary)">Feedback für {f.leader_name}</p>
				<p class="text-sm" style="color: var(--text-secondary)">
					Fällig bis {f.due_date}{#if days(f.due_date) <= 3 && days(f.due_date) >= 0} · <strong style="color: var(--warning)">nur noch {days(f.due_date)} Tage</strong>{/if} · ca. 5 Minuten
				</p>
			</div>
			{#if f.feedback_link}
				<a href={f.feedback_link} class="cta">Jetzt starten</a>
			{/if}
		</div>
	{/each}
	{#if loaded && open.length === 0 && done.length > 0}
		<Card><p style="color: var(--text-primary)">🎉 Danke! Du hast alle Feedbacks abgegeben.</p></Card>
	{/if}
	{#each done as f (f.participation_id)}
		<div class="glass-surface flex items-center gap-3 p-4">
			<span class="tick" aria-hidden="true">✓</span>
			<div>
				<p style="color: var(--text-primary)">{f.leader_name} <span class="text-xs" style="color: var(--text-muted)">· {f.round_name}</span></p>
				<p class="text-sm" style="color: var(--text-secondary)">Abgegeben am {f.completed_date}</p>
			</div>
		</div>
	{/each}
</div>

<details class="mt-5 text-sm" style="color: var(--text-secondary)">
	<summary class="cursor-pointer py-2">Kann ich meine Antworten später nochmal ansehen?</summary>
	<p class="pb-2">
		Nein – genau das schützt deine Anonymität, denn es gibt keine Verknüpfung zwischen dir und deinen Antworten.
		Direkt nach dem Absenden kannst du sie auf der Abschlussseite über „Antworten drucken / als PDF speichern“ sichern.
	</p>
</details>

<style>
	.trust {
		background: var(--surface-glass-strong);
		border: 1px solid var(--border-subtle);
		border-left: 4px solid var(--success);
		border-radius: var(--radius-md);
		padding: 0.9rem 1rem;
		font-size: 0.875rem;
		color: var(--text-primary);
	}
	.trust ul {
		margin-top: 0.35rem;
		padding-left: 1.1rem;
		list-style: disc;
		color: var(--text-secondary);
	}
	.fb-card {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}
	@media (min-width: 640px) {
		.fb-card {
			flex-direction: row;
			align-items: center;
			justify-content: space-between;
		}
	}
	.cta {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 48px;
		padding: 0 1.5rem;
		border-radius: var(--radius-sm);
		background: var(--accent);
		color: var(--accent-contrast);
		font-weight: 600;
	}
	.tick {
		display: inline-flex;
		width: 2rem;
		height: 2rem;
		align-items: center;
		justify-content: center;
		border-radius: 999px;
		background: var(--success);
		color: #fff;
		font-weight: 700;
	}
</style>
