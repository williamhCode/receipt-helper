<script lang="ts">
	import { getInitials, fetchPeople, updatePerson, type Person } from '$lib/utils.js';

	let { 
		people = $bindable(),
		onUpdate,
		onPersonRenamed,
		group
	}: {
		people: string[];
		onUpdate: (newPeople: string[]) => Promise<void>;
		onPersonRenamed?: () => Promise<void>;
		group?: any; // Group object to check receipts
	} = $props();

	let newMemberName = $state('');
	let showAddForm = $state(false);
	let editingPerson = $state<string | null>(null);
	let editingName = $state('');
	let allPeople: Person[] = $state([]);
	let loading = $state(false);
	let error = $state('');
	// DOM element reference - not reactive state
	let editInput: HTMLInputElement;
	// Shake animation state
	let shakingPerson = $state<string | null>(null);

	// Load all people when component mounts
	async function loadPeople() {
		try {
			allPeople = await fetchPeople();
		} catch (err) {
			console.error('Failed to load people:', err);
			allPeople = [];
		}
	}

	// Load people on mount
	$effect(() => {
		loadPeople();
	});

	async function addMember() {
		if (!newMemberName.trim()) return;
		
		try {
			const updatedPeople = [...people, newMemberName.trim()];
			await onUpdate(updatedPeople);
			people = updatedPeople;
			newMemberName = '';
			showAddForm = false;
			// Reload people list since we might have created a new person
			await loadPeople();
		} catch (error) {
			console.error('Failed to add member:', error);
		}
	}

	function checkPersonInReceipts(personName: string): boolean {
		for (const receipt of group.receipts) {
			if (receipt.paid_by === personName) {
        return true;
			}
			
			if (receipt.people.includes(personName)) {
        return true;
			}
		}

    return false;
	}

	function triggerShake(personName: string) {
		shakingPerson = personName;
		setTimeout(() => {
			shakingPerson = null;
		}, 300);
	}

	async function removeMember(memberToRemove: string) {
		try {
			if (checkPersonInReceipts(memberToRemove)) {
				triggerShake(memberToRemove);
				return;
			}

			const updatedPeople = people.filter(person => person !== memberToRemove);
			await onUpdate(updatedPeople);
			people = updatedPeople;
			error = ''; // Clear any previous errors
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to remove member';
		}
	}

	function cancelAdd() {
		newMemberName = '';
		showAddForm = false;
	}

	function startEditing(personName: string) {
		editingPerson = personName;
		editingName = personName;
		error = '';
		// Focus and select the input after it's rendered
		setTimeout(() => {
			if (editInput) {
				editInput.focus();
				editInput.select();
			}
		}, 0);
	}

	function cancelEditing() {
		editingPerson = null;
		editingName = '';
		error = '';
	}

	async function saveEdit() {
		if (!editingName.trim() || editingName.trim() === editingPerson || !editingPerson) {
			cancelEditing();
			return;
		}

		try {
			loading = true;
			error = '';

			// Find the person object by name
			const person = allPeople.find(p => p.name === editingPerson);
			if (!person) {
				throw new Error('Person not found');
			}

			// Update the person's name in the backend
			await updatePerson(person.id, editingName.trim());
			
			// Update the local people array
			const updatedPeople = people.map(p => p === editingPerson ? editingName.trim() : p);
			await onUpdate(updatedPeople);
			people = updatedPeople;

			// Reload people list to get updated data
			await loadPeople();

			// Notify parent component to refresh receipt data
			if (onPersonRenamed) {
				await onPersonRenamed();
			}

			cancelEditing();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to update name';
		} finally {
			loading = false;
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter') {
			saveEdit();
		} else if (event.key === 'Escape') {
			cancelEditing();
		}
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

	{#if error}
		<div class="text-red-600 text-sm bg-red-50 border border-red-200 rounded p-2">
			{error}
		</div>
	{/if}

	<div class="flex flex-wrap gap-2">
		{#each people as person}
			<div class="group relative bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-sm flex items-center space-x-2 transition-all duration-200"
				 class:animate-shake={shakingPerson === person}>
				<span class="font-medium text-xs bg-blue-200 text-blue-900 w-7 h-6 rounded-full flex items-center justify-center">
					{getInitials(person)}
				</span>
				
				{#if editingPerson === person}
					<!-- Editing mode -->
					<input
						type="text"
						bind:value={editingName}
						onkeydown={handleKeydown}
						onblur={saveEdit}
						class="bg-white border border-blue-300 rounded px-1 py-0.5 text-sm min-w-20 focus:outline-none focus:ring-1 focus:ring-blue-500"
						disabled={loading}
						bind:this={editInput}
					/>
				{:else}
					<!-- Display mode -->
					<span 
						onclick={() => startEditing(person)}
						class="cursor-pointer hover:bg-blue-200 rounded px-1 transition-colors"
						title="Click to rename"
					>
						{person}
					</span>
				{/if}

				{#if editingPerson !== person}
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
				{/if}
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

<style>
	@keyframes shake {
		0%, 100% { transform: translateX(0); }
		25% { transform: translateX(-3px); }
		75% { transform: translateX(3px); }
	}
	
	.animate-shake {
		animation: shake 0.3s ease-in-out;
	}
</style>
