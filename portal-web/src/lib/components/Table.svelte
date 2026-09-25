<script lang="ts">
	export interface Column<T> {
		key: string;
		label: string;
		render?: (row: T) => string;
	}

	let {
		columns,
		rows,
		emptyText = 'Keine Daten vorhanden.'
	}: {
		columns: Column<Record<string, unknown>>[];
		rows: Record<string, unknown>[];
		emptyText?: string;
	} = $props();
</script>

<div class="glass-surface overflow-x-auto">
	<table class="w-full text-left text-sm">
		<thead>
			<tr class="border-b" style="border-color: var(--border-subtle)">
				{#each columns as col (col.key)}
					<th class="px-4 py-3 font-semibold" style="color: var(--text-secondary)">{col.label}</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#if rows.length === 0}
				<tr>
					<td colspan={columns.length} class="px-4 py-6 text-center" style="color: var(--text-muted)">
						{emptyText}
					</td>
				</tr>
			{:else}
				{#each rows as row, i (i)}
					<tr class="border-b last:border-0" style="border-color: var(--border-subtle)">
						{#each columns as col (col.key)}
							<td class="px-4 py-3" style="color: var(--text-primary)">
								{col.render ? col.render(row) : (row[col.key] ?? '')}
							</td>
						{/each}
					</tr>
				{/each}
			{/if}
		</tbody>
	</table>
</div>
