<script lang="ts">
	// Nur in der Entwicklung sichtbar: schneller Wechsel der Ansicht (Admin / Führungskraft / Mitarbeiter).
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import { auth } from '$lib/stores/auth.svelte';

	interface Persona { title: string; personalnummer: string; full_name: string }
	let personas = $state<Persona[]>([]);

	onMount(async () => {
		try {
			personas = await api.get<Persona[]>('/dev/personas');
		} catch {
			personas = [];
		}
	});

	async function switchTo(e: Event) {
		const pnr = (e.target as HTMLSelectElement).value;
		if (!pnr) return;
		const r = await api.post<{ access_token: string }>('/auth/dev-login', { personalnummer: pnr });
		auth.setToken(r.access_token);
		auth.setKiosk(false);
		window.location.href = '/dashboard';
	}
</script>

{#if personas.length}
	<label class="block text-[11px]" style="color: var(--text-muted)">🛠 Ansicht wechseln (Dev)
		<select onchange={switchTo} class="glass-surface mt-1 w-full rounded px-2 py-2 text-xs" style="color: var(--text-primary)">
			<option value="">{auth.user?.full_name ?? '–'}</option>
			{#each personas as p (p.personalnummer)}<option value={p.personalnummer}>{p.title}</option>{/each}
		</select>
	</label>
{/if}
