<script lang="ts">
	import { getInitials } from '$lib/utils';

	let {
		receiptPeople = $bindable(),
		groupPeople,
		onUpdate
	}: {
		receiptPeople: string[];
		groupPeople: string[];
		onUpdate: (newPeople: string[]) => Promise<void>;
	} = $props();

	let showAddForm = $state(false);

	// People from group who aren't in this receipt yet
	const availablePeople = $derived(
		groupPeople.filter(person => !receiptPeople.includes(person))
	);

	async function addMember(memberToAdd: string) {
		try {
			const updatedPeople = [...receiptPeople, memberToAdd];
			await onUpdate(updatedPeople);
			receiptPeople = updatedPeople;
			showAddForm = false;
		} catch (error) {
			console.error('Failed to add member to receipt:', error);
		}
	}

	async function removeMember(memberToRemove: string) {
		try {
			const updatedPeople = receiptPeople.filter(person => person !== memberToRemove);
			await onUpdate(updatedPeople);
			receiptPeople = updatedPeople;
		} catch (error) {
			console.error('Failed to remove member from receipt:', error);
		}
	}
</script>

<div class="space-y-2">
	<div class="flex items-center justify-between">
		<h6 class="text-sm font-medium text-gray-600">Receipt Members</h6>
		{#if availablePeople.length > 0 && !showAddForm}
			<button
				onclick={() => showAddForm = true}
				class="text-xs bg-green-500 text-white px-1.5 py-0.5 rounded hover:bg-green-600 transition-colors"
			>
				+ Add
			</button>
		{/if}
	</div>

	<div class="flex flex-wrap gap-1">
		{#each receiptPeople as person}
			<div class="group relative bg-green-100 text-green-800 px-2 py-1 rounded text-xs flex items-center space-x-1">
				<span class="font-medium text-xs bg-green-200 text-green-900 w-5 h-4 rounded-full flex items-center justify-center text-[10px]">
					{getInitials(person)}
				</span>
				<span class="text-xs">{person}</span>
				<button
					onclick={() => removeMember(person)}
					class="opacity-0 group-hover:opacity-100 text-green-600 hover:text-red-600 transition-all"
					title="Remove {person} from this receipt"
          aria-label="Remove {person} from this receipt"
				>
					<svg class="w-2 h-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
					</svg>
				</button>
			</div>
		{/each}

		{#if showAddForm && availablePeople.length > 0}
			<div class="flex flex-wrap gap-1">
				{#each availablePeople as person}
					<button
						onclick={() => addMember(person)}
						class="bg-gray-200 text-gray-700 px-2 py-0.5 rounded text-xs hover:bg-gray-300 transition-colors flex items-center space-x-1"
					>
						<span class="font-medium text-xs bg-gray-300 text-gray-700 w-4 h-4 rounded-full flex items-center justify-center text-[10px]">
							{getInitials(person)}
						</span>
						<span class="text-xs">{person}</span>
					</button>
				{/each}
				<button
					onclick={() => showAddForm = false}
					class="bg-red-200 text-red-700 px-2 py-0.5 rounded text-xs hover:bg-red-300 transition-colors"
				>
					Cancel
				</button>
			</div>
		{/if}
	</div>
</div>
