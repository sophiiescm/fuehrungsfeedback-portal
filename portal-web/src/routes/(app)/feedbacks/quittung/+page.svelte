<script lang="ts">
	// Ziel nach dem Absenden in LimeSurvey. Die Antworten kommen im URL-Fragment (nie zum Server)
	// und werden nur auf diesem Gerät gespeichert.
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { decodeFragment, saveReceipt } from '$lib/receipts';

	let saved = $state(false);
	let kiosk = $state(false);

	onMount(() => {
		const { receipt } = decodeFragment(window.location.hash);
		history.replaceState(null, '', '/feedbacks/quittung'); // Fragment sofort aus der Adresszeile/History entfernen
		kiosk = auth.kiosk;
		const pnr = auth.user?.personalnummer;
		if (receipt && pnr && !kiosk) {
			saveReceipt(pnr, receipt);
			saved = true;
		}
		const t = setTimeout(() => goto('/feedbacks', { replaceState: true }), 3500);
		return () => clearTimeout(t);
	});
</script>

<div class="mx-auto mt-10 max-w-md text-center">
	<div class="glass-surface p-8">
		<p class="text-5xl">🎉</p>
		<h1 class="mt-3 text-2xl font-bold" style="color: var(--text-primary)">Danke für dein Feedback!</h1>
		<p class="mt-2 text-sm" style="color: var(--text-secondary)">Deine Antworten sind angekommen und können nicht mehr geändert werden.</p>
		{#if saved}
			<p class="mt-3 text-sm" style="color: var(--success)">🔒 Eine Kopie deiner Antworten liegt nur auf diesem Gerät – nicht auf dem Server.</p>
		{:else if kiosk}
			<p class="mt-3 text-sm" style="color: var(--text-muted)">Auf diesem Gemeinschaftsgerät wird aus Datenschutzgründen nichts gespeichert.</p>
		{/if}
		<a href="/feedbacks" class="mt-5 inline-block text-sm underline" style="color: var(--accent)">Weiter zu „Meine Feedbacks“</a>
	</div>
</div>
