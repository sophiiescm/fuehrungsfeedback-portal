<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { api } from '$lib/api/client';
	import Sidebar from '$lib/components/Sidebar.svelte';

	let { children } = $props();
	let loading = $state(true);

	// Kiosk-Modus (Code-Login): automatischer Logout nach 3 Minuten Inaktivitaet
	$effect(() => {
		if (!browser || !auth.kiosk) return;
		let timer: ReturnType<typeof setTimeout>;
		const reset = () => {
			clearTimeout(timer);
			timer = setTimeout(() => auth.logout(), 3 * 60 * 1000);
		};
		const events = ['click', 'keydown', 'touchstart', 'mousemove'];
		events.forEach((e) => window.addEventListener(e, reset));
		reset();
		return () => {
			clearTimeout(timer);
			events.forEach((e) => window.removeEventListener(e, reset));
		};
	});

	$effect(() => {
		if (!browser) return;
		if (!auth.token) {
			goto('/login');
			return;
		}
		if (!auth.user) {
			api
				.get<typeof auth.user>('/auth/me')
				.then((me) => {
					if (me) auth.setUser(me);
					loading = false;
				})
				.catch(() => goto('/login'));
		} else {
			loading = false;
		}
	});
</script>

{#if loading}
	<div class="flex min-h-screen items-center justify-center" style="color: var(--text-secondary)">
		Lädt…
	</div>
{:else}
	<Sidebar />
	<main class="app-main mx-auto min-h-screen max-w-6xl p-4 lg:ml-[calc(var(--sidebar-width)+2rem)] lg:max-w-none lg:p-8">
		{@render children()}
	</main>
{/if}
