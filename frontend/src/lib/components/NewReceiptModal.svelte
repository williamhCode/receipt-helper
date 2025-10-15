<script lang="ts">
	import type { Group } from '$lib/types';

	let { 
		show = $bindable(), 
		group, 
		onSubmit 
	}: { 
		show: boolean; 
		group: Group | null; 
		onSubmit: (data: { name: string; paidBy: string; entries: string; people: string[] }) => Promise<void>;
	} = $props();

	let newReceiptName = $state('');
	let newReceiptEntries = $state('');
	let newReceiptPaidBy = $state('');

	// Clone people from the most recent receipt, or use all group people if no receipts exist
	const defaultPeople = $derived(() => {
		if (!group) return [];
		if (group.receipts.length === 0) return [...group.people];
		
		// Get the most recent receipt (assuming they're ordered by creation)
		const mostRecentReceipt = group.receipts[group.receipts.length - 1];
		return mostRecentReceipt.people ? [...mostRecentReceipt.people] : [...group.people];
	});

	async function handleSubmit() {
		if (!newReceiptName.trim()) return;
		
		await onSubmit({
			name: newReceiptName,
			paidBy: newReceiptPaidBy,
			entries: newReceiptEntries,
			people: defaultPeople()
		});

		// Reset form
		newReceiptName = '';
		newReceiptEntries = '';
		newReceiptPaidBy = '';
		show = false;
	}

	function handleClose() {
		show = false;
		newReceiptName = '';
		newReceiptEntries = '';
		newReceiptPaidBy = '';
	}
</script>

{#if show}
	<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
		<div class="bg-white rounded-lg p-6 w-full max-w-md">
			<h3 class="text-lg font-semibold text-gray-800 mb-4">Create New Receipt</h3>
			
			<div class="space-y-4">
				<div>
					<label class="block text-sm font-medium text-gray-700 mb-1">Receipt Name *</label>
					<input
						type="text"
						bind:value={newReceiptName}
						placeholder="e.g., Grocery Store, Restaurant"
						class="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
					/>
				</div>
				
				{#if group}
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Paid By</label>
						<select bind:value={newReceiptPaidBy} class="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
							<option value="">Select who paid</option>
							{#each defaultPeople() as person}
								<option value={person}>{person}</option>
							{/each}
						</select>
					</div>

					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Receipt Members</label>
						<div class="text-sm text-gray-600 bg-blue-50 p-2 rounded border">
							{defaultPeople().join(', ')}
							<div class="text-xs text-gray-500 mt-1">
								{group.receipts.length > 0 ? 'Copied from most recent receipt' : 'Using all group members'}
							</div>
						</div>
					</div>
				{/if}
				
				<div>
					<label class="block text-sm font-medium text-gray-700 mb-1">
						Entries (Optional JSON)
					</label>
					<textarea
						bind:value={newReceiptEntries}
						placeholder={`[{"name": "Apples", "price": 3.99, "taxable": true}]`}
						rows="4"
						class="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
					></textarea>
					<p class="text-xs text-gray-500 mt-1">
						Format: {`[{"name": "Item", "price": 0.00, "taxable": true}]`}
					</p>
				</div>
			</div>
			
			<div class="flex space-x-3 mt-6">
				<button
					onclick={handleSubmit}
					disabled={!newReceiptName.trim()}
					class="flex-1 bg-blue-500 text-white py-2 rounded hover:bg-blue-600 disabled:opacity-50 transition-colors"
				>
					Create Receipt
				</button>
				<button
					onclick={handleClose}
					class="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
				>
					Cancel
				</button>
			</div>
		</div>
	</div>
{/if}
