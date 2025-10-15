<script lang="ts">
	import { updateGroup } from '$lib/api';

	let { 
		groupId,
		initialName,
		onNameUpdate 
	}: {
		groupId: number;
		initialName: string;
		onNameUpdate: (newName: string) => void;
	} = $props();

	let isEditing = $state(false);
	let name = $state(initialName);
	let inputElement: HTMLInputElement;

	// Update local name when initialName changes
	$effect(() => {
		name = initialName;
	});

	// Focus when entering edit mode
	$effect(() => {
		if (isEditing && inputElement) {
			inputElement.focus();
			inputElement.select();
		}
	});

	async function saveEdit() {
		if (name.trim() === initialName || !name.trim()) {
			isEditing = false;
			name = initialName;
			return;
		}

		try {
			const updatedGroup = await updateGroup(groupId, { name: name.trim() });
			onNameUpdate(updatedGroup.name);
			isEditing = false;
		} catch (err) {
			console.error('Failed to update group name:', err);
			name = initialName; // Reset on error
			isEditing = false;
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter') {
			saveEdit();
		} else if (event.key === 'Escape') {
			name = initialName;
			isEditing = false;
		}
	}
</script>

{#if isEditing}
	<input
		type="text"
		bind:value={name}
		bind:this={inputElement}
		onkeydown={handleKeydown}
		onblur={saveEdit}
		class="text-3xl font-bold bg-transparent border-b-2 border-blue-500 focus:outline-none focus:border-blue-700 text-gray-800 min-w-[200px]"
		maxlength="255"
	/>
{:else}
	<h1 
		onclick={() => isEditing = true}
		class="text-3xl font-bold text-gray-800 cursor-pointer hover:text-blue-600 transition-colors duration-200"
		title="Click to edit group name"
	>
		{initialName}
	</h1>
{/if}
