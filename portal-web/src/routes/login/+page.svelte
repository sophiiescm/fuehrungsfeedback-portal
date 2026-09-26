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

	let devUsers = $state<DevUser[]>([]);
	let devLoginAvailable = $state(false);
	let personalnummer = $state('');
	let code = $state('');
	let error = $state('');

	onMount(async () => {
		try {
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
			await goto('/dashboard');
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
			await goto('/feedbacks');
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Anmeldung fehlgeschlagen';
		}
	}

	function loginWithSso() {
		const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
		window.location.href = `${apiBase}/auth/oidc/login`;
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
						<p class="mb-2 text-xs" style="color: var(--text-muted)">
							Dev-Login (nur lokale Entwicklung)
						</p>
						<div class="flex flex-col gap-2">
							{#each devUsers as user (user.personalnummer)}
								<button
									onclick={() => loginAsDevUser(user.personalnummer)}
									class="glass-surface flex items-center justify-between rounded-[var(--radius-sm)] px-3 py-2 text-left text-sm"
									style="color: var(--text-primary)"
								>
									<span>{user.full_name}</span>
									<span class="text-xs" style="color: var(--text-muted)">{user.roles.join(', ')}</span>
								</button>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		</Card>
	</div>
</div>
