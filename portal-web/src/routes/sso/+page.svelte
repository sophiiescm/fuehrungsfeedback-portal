<script lang="ts">
	// Einstieg aus der Mitarbeiter-App: <portal>/sso#assertion=<signierte Einmal-Assertion>
	// (im Fragment, damit sie nicht in Server-Logs landet).
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { api, ApiError } from '$lib/api/client';

	let error = $state('');
	onMount(async () => {
		const assertion = new URLSearchParams(window.location.hash.slice(1)).get('assertion');
		history.replaceState(null, '', '/sso');
		if (!assertion) {
			error = 'Keine Anmeldeinformation von der Mitarbeiter-App erhalten.';
			return;
		}
		try {
			const r = await api.post<{ access_token: string }>('/auth/app-sso', { assertion });
			auth.setToken(r.access_token);
			await goto('/feedbacks', { replaceState: true });
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Anmeldung fehlgeschlagen';
		}
	});
</script>

<div class="flex min-h-screen items-center justify-center p-4" style="color: var(--text-primary)">
	{#if error}
		<div class="text-center"><p style="color: var(--danger)">{error}</p><a href="/login" class="underline">Andere Anmeldung wählen</a></div>
	{:else}
		<p>Anmeldung über die Mitarbeiter-App …</p>
	{/if}
</div>
