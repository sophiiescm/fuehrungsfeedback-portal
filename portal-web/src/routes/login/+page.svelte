<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth.svelte';
	import { api, ApiError } from '$lib/api/client';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';

	interface DevUser {
		personalnummer: string;
		full_name: string;
		roles: string[];
	}

	interface Persona { title: string; personalnummer: string; full_name: string; note: string }
	let personas = $state<Persona[]>([]);
	let devUsers = $state<DevUser[]>([]);
	let devLoginAvailable = $state(false);
	let personalnummer = $state('');
	let code = $state('');
	let error = $state('');

	onMount(async () => {
		if (auth.token) {
			await goto('/dashboard', { replaceState: true });
			return;
		}
		try {
			personas = await api.get<Persona[]>('/dev/personas');
			devUsers = await api.get<DevUser[]>('/auth/dev-login/users');
			devLoginAvailable = true;
		} catch {
			devLoginAvailable = false;
		}
	});

	async function loginAsDevUser(pnr: string) {
		error = '';
		try {
			const result = await api.post<{ access_token: string }>('/auth/dev-login', {
				personalnummer: pnr
			});
			auth.setToken(result.access_token);
			await goto('/dashboard', { replaceState: true });
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Anmeldung fehlgeschlagen';
		}
	}

	async function loginWithCode(event: SubmitEvent) {
		event.preventDefault();
		error = '';
		try {
			const result = await api.post<{ access_token: string }>('/auth/code-login', {
				personalnummer: personalnummer.trim(),
				code: code.trim().toUpperCase()
			});
			auth.setToken(result.access_token);
			auth.setKiosk(true);
			await goto('/feedbacks', { replaceState: true });
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Anmeldung fehlgeschlagen';
		}
	}

	async function loginWithSso() {
		error = '';
		try {
			const r = await api.get<{ url: string }>('/auth/oidc/login');
			window.location.href = r.url;
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'SSO ist nicht verfügbar';
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center p-4">
	<div class="w-full max-w-md">
		<Card>
			<h1 class="mb-6 text-center text-2xl font-bold" style="color: var(--text-primary)">
				Führungsfeedback-Portal
			</h1>

			<div class="flex flex-col gap-3">
				<Button variant="primary" onclick={loginWithSso}>Mit Single Sign-On anmelden</Button>

				<div class="my-2 text-center text-xs" style="color: var(--text-muted)">oder</div>

				<form class="flex flex-col gap-2" onsubmit={loginWithCode}>
					<input
						type="text"
						placeholder="Personalnummer"
						bind:value={personalnummer}
						class="glass-surface rounded-[var(--radius-sm)] px-3 py-2 text-sm"
						style="color: var(--text-primary)"
					/>
					<input
						type="password"
						placeholder="Einmalcode"
						bind:value={code}
						class="glass-surface rounded-[var(--radius-sm)] px-3 py-2 text-sm"
						style="color: var(--text-primary)"
					/>
					<Button type="submit" variant="secondary">Mit Code anmelden</Button>
				</form>

				{#if error}
					<p class="text-sm" style="color: var(--danger)">{error}</p>
				{/if}

				{#if devLoginAvailable}
					<div class="mt-4 border-t pt-4" style="border-color: var(--border-subtle)">
						<p class="mb-2 text-xs font-semibold" style="color: var(--text-muted)">🛠 Entwickler-Schnellzugriff (nur lokale Entwicklung)</p>
						<div class="flex flex-col gap-2">
							{#each personas as p (p.personalnummer)}
								<button onclick={() => loginAsDevUser(p.personalnummer)} class="glass-surface flex flex-col rounded-[var(--radius-sm)] px-3 py-2 text-left text-sm" style="color: var(--text-primary); min-height: 52px">
									<span class="font-semibold">{p.title}</span>
									<span class="text-xs" style="color: var(--text-secondary)">{p.full_name} · {p.note}</span>
								</button>
							{/each}
						</div>
						<details class="mt-3 text-xs" style="color: var(--text-muted)">
							<summary class="cursor-pointer py-1">Weitere Personen</summary>
							<div class="mt-2 flex flex-col gap-1">
								{#each devUsers as user (user.personalnummer)}
									<button onclick={() => loginAsDevUser(user.personalnummer)} class="flex items-center justify-between rounded px-2 py-2 text-left" style="color: var(--text-primary)">
										<span>{user.full_name}</span><span>{user.roles.join(', ')}</span>
									</button>
								{/each}
							</div>
						</details>
					</div>
				{/if}
			</div>
		</Card>
	</div>
</div>
