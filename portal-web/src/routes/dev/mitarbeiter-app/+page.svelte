<script lang="ts">
	// Entwickler-Simulator der Mitarbeiter-App: zeigt, wie Mitarbeitende aus der App per
	// Trusted-App-SSO ohne weiteren Login ins Führungsfeedback gelangen. Nur mit APP_ENV=dev.
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api/client';

	interface Persona { title: string; personalnummer: string; full_name: string; note: string }
	let personas = $state<Persona[]>([]);
	let who = $state('');
	let error = $state('');
	let available = $state(true);

	onMount(async () => {
		try {
			personas = (await api.get<Persona[]>('/dev/personas')).filter((p) => p.title !== 'Admin (HR)');
			who = personas[0]?.personalnummer ?? '';
		} catch {
			available = false;
		}
	});

	async function openFeedback() {
		error = '';
		try {
			const r = await api.post<{ portal_url: string }>('/dev/app-assertion', { personalnummer: who });
			window.location.href = r.portal_url;
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Fehlgeschlagen';
		}
	}
	const tiles = [
		['🏖', 'Urlaub'],
		['💶', 'Gehaltsabrechnung'],
		['📅', 'Schichtplan'],
		['📰', 'Neuigkeiten']
	];
</script>

<div class="mx-auto max-w-md p-4" style="color: var(--text-primary)">
	{#if !available}
		<p class="mt-10 text-center">Nur in der lokalen Entwicklung verfügbar.</p>
	{:else}
		<div class="glass-surface mb-4 flex items-center justify-between p-4">
			<div><p class="text-xs" style="color: var(--text-muted)">Mitarbeiter-App (Simulation)</p><p class="font-bold">Willkommen, {personas.find((p) => p.personalnummer === who)?.full_name ?? ''}</p></div>
			<select bind:value={who} class="glass-surface rounded px-2 py-2 text-xs">
				{#each personas as p (p.personalnummer)}<option value={p.personalnummer}>{p.title}</option>{/each}
			</select>
		</div>
		<div class="grid grid-cols-2 gap-3">
			{#each tiles as [icon, label]}
				<div class="glass-surface flex flex-col items-center gap-1 p-5 text-sm opacity-70"><span class="text-3xl">{icon}</span>{label}</div>
			{/each}
			<button onclick={openFeedback} class="col-span-2 flex items-center justify-center gap-3 rounded-[var(--radius-lg)] p-5 text-lg font-semibold" style="background: var(--accent); color: var(--accent-contrast); min-height: 72px">
				<span class="text-3xl">💬</span> Führungsfeedback
			</button>
		</div>
		{#if error}<p class="mt-3 text-sm" style="color: var(--danger)">{error}</p>{/if}
		<p class="mt-4 text-xs" style="color: var(--text-muted)">
			Die App erzeugt beim Tippen eine kurzlebige, signierte Einmal-Assertion (60 s) und öffnet das Portal – ohne weitere Anmeldung. So läuft es später mit der echten Mitarbeiter-App.
		</p>
		<a href="/login" class="mt-3 block text-center text-xs underline">Zurück zum Login</a>
	{/if}
</div>
