<script lang="ts">
	// Persönliche Sprache für Umfragen: jede Person wählt selbst (gilt für alle Fragebögen, die diese Sprache anbieten).
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import { auth } from '$lib/stores/auth.svelte';

	interface Lang { code: string; name: string }
	let available = $state<Lang[]>([]);
	let mine = $state('de');
	let saved = $state(false);

	onMount(async () => {
		try {
			const r = await api.get<{ available: Lang[]; mine: string }>('/languages');
			available = r.available;
			mine = r.mine;
		} catch {
			available = [];
		}
	});

	async function change(e: Event) {
		mine = (e.target as HTMLSelectElement).value;
		await api.put('/auth/me/language', { language: mine });
		if (auth.user) auth.setUser({ ...auth.user, language: mine });
		saved = true;
		setTimeout(() => (saved = false), 1800);
	}
</script>

{#if available.length > 1}
	<label class="block text-[11px]" style="color: var(--text-muted)">🌐 Sprache der Umfragen
		<select value={mine} onchange={change} class="glass-surface mt-1 w-full rounded px-2 py-2 text-xs" style="color: var(--text-primary)">
			{#each available as l (l.code)}<option value={l.code}>{l.name}</option>{/each}
		</select>
		{#if saved}<span style="color: var(--success)">✓ gespeichert</span>{/if}
	</label>
{/if}
