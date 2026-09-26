<script lang="ts">
	// Fenster in der Seitenmitte (Desktop) bzw. als Sheet von unten (Handy). Schließen: ✕, Esc, Klick daneben.
	let {
		open,
		title,
		onclose,
		wide = false,
		children
	}: { open: boolean; title: string; onclose: () => void; wide?: boolean; children?: import('svelte').Snippet } = $props();
</script>

<svelte:window onkeydown={(e) => open && e.key === 'Escape' && onclose()} />

{#if open}
	<div class="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={title}>
		<button class="absolute inset-0 cursor-default" style="background: rgba(10, 12, 25, 0.5)" aria-label="Fenster schließen" onclick={onclose}></button>
		<div class="sheet glass-surface relative flex max-h-[92vh] w-full flex-col" class:wide style="background: var(--surface-glass-strong)">
			<div class="flex items-center justify-between gap-3 border-b p-4" style="border-color: var(--border-subtle)">
				<h2 class="text-lg font-semibold" style="color: var(--text-primary)">{title}</h2>
				<button class="close" onclick={onclose} aria-label="Schließen">✕</button>
			</div>
			<div class="overflow-y-auto p-4 sm:p-5">
				{@render children?.()}
			</div>
		</div>
	</div>
{/if}

<style>
	.sheet {
		max-width: 40rem;
		border-radius: var(--radius-lg) var(--radius-lg) 0 0;
		padding-bottom: env(safe-area-inset-bottom);
	}
	.sheet.wide {
		max-width: 52rem;
	}
	@media (min-width: 640px) {
		.sheet {
			border-radius: var(--radius-lg);
		}
	}
	.close {
		width: 40px;
		height: 40px;
		border-radius: 999px;
		color: var(--text-secondary);
		background: var(--surface-glass);
	}
</style>
