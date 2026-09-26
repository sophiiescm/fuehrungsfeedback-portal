<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { api, ApiError } from '$lib/api/client';

	let error = $state('');
	onMount(async () => {
		const p = new URLSearchParams(window.location.search);
		try {
			const r = await api.post<{ access_token: string }>('/auth/oidc/callback', {
				code: p.get('code') ?? '',
				state: p.get('state') ?? ''
			});
			auth.setToken(r.access_token);
			await goto('/dashboard');
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'SSO-Anmeldung fehlgeschlagen';
		}
	});
</script>

<div class="flex min-h-screen items-center justify-center p-4" style="color: var(--text-primary)">
	{#if error}
		<div class="text-center"><p style="color: var(--danger)">{error}</p><a href="/login" class="underline">Zurück zur Anmeldung</a></div>
	{:else}
		<p>Anmeldung läuft …</p>
	{/if}
</div>
