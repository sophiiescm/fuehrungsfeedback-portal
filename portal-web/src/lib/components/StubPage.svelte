<script lang="ts">
	import Card from './Card.svelte';

	let { title, phase }: { title: string; phase: string } = $props();
</script>

<h1 class="mb-6 text-2xl font-bold" style="color: var(--text-primary)">{title}</h1>
<Card>
	<p style="color: var(--text-secondary)">Diese Ansicht wird in {phase} umgesetzt.</p>
</Card>
