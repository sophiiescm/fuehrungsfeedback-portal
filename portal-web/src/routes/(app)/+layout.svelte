<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { api } from '$lib/api/client';
	import Sidebar from '$lib/components/Sidebar.svelte';

	let { children } = $props();
	let loading = $state(true);

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
	<main class="min-h-screen p-4 pt-20 md:ml-[calc(var(--sidebar-width)+2rem)] md:p-8">
		{@render children()}
	</main>
{/if}
