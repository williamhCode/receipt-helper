<script lang="ts">
	import { getInitials } from '$lib/utils.js';

	let { 
		people = $bindable(),
		onUpdate
	}: {
		people: string[];
		onUpdate: (newPeople: string[]) => Promise<void>;
	} = $props();

	let newMemberName = $state('');
	let showAddForm = $state(false);

	async function addMember() {
		if (!newMemberName.trim()) return;
		
		try {
			const updatedPeople = [...people, newMemberName.trim()];
			await onUpdate(updatedPeople);
			people = updatedPeople;
			newMemberName = '';
			showAddForm = false;
		} catch (error) {
			console.error('Failed to add member:', error);
		}
	}

	async function removeMember(memberToRemove: string) {
		try {
			const updatedPeople = people.filter(person => person !== memberToRemove);
			await onUpdate(updatedPeople);
			people = updatedPeople;
		} catch (error) {
			console.error('Failed to remove member:', error);
		}
	}

	function cancelAdd() {
		newMemberName = '';
		showAddForm = false;
	}
</script>

<div class="space-y-3">
	<div class="flex items-center justify-between">
		<h3 class="text-2xl font-semibold text-gray-700">Group Members</h3>
		{#if !showAddForm}
			<button
				onclick={() => showAddForm = true}
				class="text-sm bg-blue-500 text-white px-2.5 py-1 rounded hover:bg-blue-600 transition-colors"
			>
        + Add
			</button>
		{/if}
	</div>

	<div class="flex flex-wrap gap-2">
		{#each people as person}
			<div class="group relative bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-sm flex items-center space-x-2">
				<span class="font-medium text-xs bg-blue-200 text-blue-900 w-6 h-6 rounded-full flex items-center justify-center">
					{getInitials(person)}
				</span>
				<span>{person}</span>
				<button
					onclick={() => removeMember(person)}
					class="opacity-0 group-hover:opacity-100 text-blue-600 hover:text-red-600 transition-all"
					title="Remove {person}"
          aria-label="Remove {person} from group"
				>
					<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
					</svg>
				</button>
			</div>
		{/each}

		{#if showAddForm}
			<div class="flex items-center space-x-2 bg-gray-100 px-3 py-1 rounded-full">
				<!-- svelte-ignore a11y_autofocus -->
				<input
					type="text"
					bind:value={newMemberName}
					placeholder="Member name"
					class="bg-transparent border-none outline-none text-sm w-24"
					onkeydown={(e) => {
						if (e.key === 'Enter') addMember();
						if (e.key === 'Escape') cancelAdd();
					}}
					autofocus
				/>
				<!-- svelte-ignore a11y_consider_explicit_label -->
				<button
					onclick={addMember}
					disabled={!newMemberName.trim()}
					class="text-green-600 hover:text-green-800 disabled:opacity-50"
				>
					<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
					</svg>
				</button>
				<button
					onclick={cancelAdd}
					class="text-red-600 hover:text-red-800"
          aria-label="Cancel adding member"
				>
					<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
					</svg>
				</button>
			</div>
		{/if}
	</div>
</div>
