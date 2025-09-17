<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { 
		fetchGroup, 
		createReceipt,
		updateGroup,
		updateReceipt,
		handleError, 
		calculateCombinedCosts, 
		calculateReceiptCosts,
		calculateReceiptTotal,
		getUnprocessedReceiptsTotal,
		getInitials,
		type Group, 
		type Receipt,
		type ReceiptEntry
	} from '$lib/utils.js';
	import ErrorDisplay from '$lib/components/ErrorDisplay.svelte';
	import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
	import NewReceiptModal from '$lib/components/NewReceiptModal.svelte';
	import GroupMembersManager from '$lib/components/GroupMembersManager.svelte';
	import ReceiptMembersManager from '$lib/components/ReceiptMembersManager.svelte';

	// State using runes
	let group = $state<Group | null>(null);
	let loading = $state(false);
	let error = $state('');
	let showNewReceiptForm = $state(false);

	// Derived state
	const groupId = $derived(parseInt($page.params.id));

	async function loadGroup() {
		try {
			loading = true;
			error = '';
			group = await fetchGroup(groupId);
		} catch (err) {
			error = handleError(err, 'Failed to fetch group');
		} finally {
			loading = false;
		}
	}

	async function handleUpdateGroupMembers(newPeople: string[]) {
		if (!group) return;
		await updateGroup(groupId, { people: newPeople });
		group.people = newPeople;
	}

	async function handleUpdateReceiptMembers(receiptId: number, newPeople: string[]) {
		if (!group) return;
		await updateReceipt(receiptId, { people: newPeople });
		
		// Update the receipt in the group
		const receipt = group.receipts.find(r => r.id === receiptId);
		if (receipt) {
			receipt.people = newPeople;
			group = group; // Force reactivity
		}
	}

	async function handleCreateReceipt(data: { name: string; paidBy: string; entries: string; people: string[] }) {
		if (!group) return;
		
		try {
			loading = true;
			error = '';

			let entries = [];
			if (data.entries.trim()) {
				try {
					entries = JSON.parse(data.entries);
				} catch (e) {
					throw new Error('Invalid JSON format for entries');
				}
			}

			const receiptData = {
				processed: true,
				raw_data: data.name,
				paid_by: data.paidBy || null,
				people: data.people,
				entries: entries
			};

			await createReceipt(groupId, receiptData);
			await loadGroup();
		} catch (err) {
			error = handleError(err, 'Failed to create receipt');
		} finally {
			loading = false;
		}
	}

	function updateAssignment(entryId: number, person: string, assigned: boolean) {
		if (!group) return;

		// Find the receipt and entry to update
		for (const receipt of group.receipts) {
			const entry = receipt.entries.find(e => e.id === entryId);
			if (entry) {
				if (assigned && !entry.assigned_to.includes(person)) {
					entry.assigned_to.push(person);
				} else if (!assigned) {
					entry.assigned_to = entry.assigned_to.filter(p => p !== person);
				}
				break;
			}
		}

		// Force reactivity by reassigning
		group = group;
	}

	onMount(() => {
		loadGroup();
	});
</script>

<main class="container mx-auto p-6 bg-gray-50 min-h-screen">
	<!-- Header -->
	<div class="flex items-center justify-between mb-6">
		<div class="flex items-center space-x-4">
			<button
				onclick={() => goto('/')}
				class="text-blue-600 hover:text-blue-800 flex items-center space-x-2"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
				</svg>
				<span>Back to Groups</span>
			</button>
			{#if group}
				<h1 class="text-3xl font-bold text-gray-800">Group {group.id}</h1>
			{/if}
		</div>
		
		<button
			onclick={() => showNewReceiptForm = true}
			class="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 transition-colors"
		>
			+ New Receipt
		</button>
	</div>

	<ErrorDisplay bind:error />

	{#if loading}
		<LoadingSpinner />
	{/if}

	{#if group}
		<!-- Top Section: Group Info & Combined Costs -->
		<div class="grid lg:grid-cols-2 gap-6 mb-6">
			<!-- Group Info -->
			<div class="bg-white p-6 rounded-lg shadow-md">
				<GroupMembersManager 
					bind:people={group.people} 
					onUpdate={handleUpdateGroupMembers}
				/>
				
				<div class="space-y-2 text-sm mt-4 pt-4 border-t">
					<p><span class="font-medium">Group ID:</span> <span class="font-mono text-xs bg-gray-100 px-2 py-1 rounded">{group.slug}</span></p>
					<p><span class="font-medium">Total Receipts:</span> {group.receipts.length}</p>
					<p><span class="font-medium">Unprocessed Total:</span> ${getUnprocessedReceiptsTotal(group).toFixed(2)}</p>
				</div>
			</div>

			<!-- Combined Cost Breakdown -->
			<div class="bg-gradient-to-br from-blue-50 to-indigo-50 p-6 rounded-lg border border-blue-200">
				<h3 class="text-lg font-semibold text-gray-700 mb-4">Combined Balance</h3>
				<div class="grid grid-cols-1 gap-3">
					{#each Object.entries(calculateCombinedCosts(group)) as [person, amount]}
						<div class="bg-white p-3 rounded-lg shadow-sm">
							<div class="flex justify-between items-center">
								<div class="flex items-center space-x-2">
									<span class="font-medium text-xs bg-blue-200 text-blue-900 w-6 h-6 rounded-full flex items-center justify-center">
										{getInitials(person)}
									</span>
									<span class="font-medium text-gray-700">{person}:</span>
								</div>
								<span class="font-mono font-semibold" 
									  class:text-green-600={amount < 0} 
									  class:text-red-600={amount > 0} 
									  class:text-gray-800={amount === 0}>
									{amount < 0 ? '+' : ''}{Math.abs(amount).toFixed(2)}
								</span>
							</div>
							<div class="text-xs text-gray-500 mt-1 ml-8">
								{amount < 0 ? 'Is owed' : amount > 0 ? 'Owes' : 'Even'}
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>

		<!-- Bottom Section: Horizontally Scrollable Receipts -->
		<div class="bg-white rounded-lg shadow-md">
			<div class="p-6 border-b">
				<h3 class="text-lg font-semibold text-gray-700">Receipts</h3>
			</div>
			
			{#if group.receipts.length === 0}
				<div class="p-12 text-center text-gray-500">
					<svg class="w-16 h-16 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
					</svg>
					<h4 class="text-lg font-medium text-gray-900 mb-2">No receipts found</h4>
					<p class="text-gray-500">Create a new receipt to get started!</p>
				</div>
			{:else}
				<div class="p-6">
					<div class="flex space-x-6 overflow-x-auto pb-4">
						{#each group.receipts as receipt}
							<div class="flex-shrink-0 w-[700px] bg-gray-50 border border-gray-200 rounded-lg p-4" style="scroll-snap-align: start;">
								<!-- Receipt Header -->
								<div class="flex justify-between items-start mb-4">
									<div>
										<h4 class="text-lg font-semibold text-gray-800">Receipt #{receipt.id}</h4>
										<p class="text-sm text-gray-500">{new Date(receipt.created_at).toLocaleDateString()}</p>
									</div>
									<span class="text-xs px-2 py-1 rounded-full" 
										  class:bg-green-100={receipt.processed}
										  class:text-green-800={receipt.processed}
										  class:bg-yellow-100={!receipt.processed}
										  class:text-yellow-800={!receipt.processed}>
										{receipt.processed ? 'Processed' : 'Pending'}
									</span>
								</div>

								<!-- Receipt Info -->
								<div class="mb-4 space-y-2 text-sm">
									<p><span class="font-medium">Total:</span> ${calculateReceiptTotal(receipt).toFixed(2)}</p>
									<p><span class="font-medium">Items:</span> {receipt.entries.length}</p>
									{#if receipt.paid_by}
										<p><span class="font-medium">Paid by:</span> 
											<span class="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs">
												{receipt.paid_by}
											</span>
										</p>
									{:else}
										<p><span class="font-medium">Paid by:</span> <span class="text-gray-500">Not specified</span></p>
									{/if}
									{#if receipt.raw_data}
										<p><span class="font-medium">Notes:</span> <span class="text-gray-600">{receipt.raw_data}</span></p>
									{/if}
								</div>

								<!-- Receipt Members Management -->
								<div class="mb-4">
									<ReceiptMembersManager 
										bind:receiptPeople={receipt.people}
										groupPeople={group.people}
										onUpdate={(newPeople) => handleUpdateReceiptMembers(receipt.id, newPeople)}
									/>
								</div>

								<!-- Items Table -->
								{#if receipt.entries.length > 0}
									<div class="mb-4">
										<h5 class="font-medium text-gray-700 mb-2">Items</h5>
										<div class="bg-white rounded border border-gray-200 overflow-hidden">
											<table class="w-full text-xs">
												<thead class="bg-gray-50">
													<tr>
														<th class="p-2 text-left font-medium text-gray-700 w-auto min-w-0">Item</th>
														<th class="p-2 text-right font-medium text-gray-700 w-16">Price</th>
														<th class="p-2 text-center font-medium text-gray-700 w-10">Tax</th>
														{#each receipt.people as person}
															<th class="p-2 text-center font-medium text-gray-700 w-10" title={person}>{getInitials(person)}</th>
														{/each}
													</tr>
												</thead>
												<tbody>
													{#each receipt.entries as entry}
														<tr class="border-t border-gray-100 hover:bg-gray-50">
															<td class="p-2 text-gray-800 text-xs pr-1" title={entry.name}>
																<div>{entry.name}</div>
															</td>
															<td class="p-2 text-gray-800 font-mono text-xs text-right w-16">${entry.price.toFixed(2)}</td>
															<td class="p-2 text-center w-10">
																<span class="w-3 h-3 rounded-full inline-block" 
																	  class:bg-green-500={entry.taxable}
																	  class:bg-gray-300={!entry.taxable}
																	  title={entry.taxable ? 'Taxable' : 'Not taxable'}>
																</span>
															</td>
															{#each receipt.people as person}
																<td class="p-2 text-center w-10">
																	<input
																		type="checkbox"
																		checked={entry.assigned_to.includes(person)}
																		onchange={(e) => updateAssignment(entry.id, person, e.currentTarget.checked)}
																		class="w-3 h-3 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
																	/>
																</td>
															{/each}
														</tr>
													{/each}
												</tbody>
											</table>
										</div>
									</div>
								{/if}

								<!-- Cost Breakdown -->
								<div class="bg-gradient-to-br from-green-50 to-emerald-50 p-3 rounded-lg border border-green-200">
									<h5 class="font-medium mb-2 text-gray-700 text-sm">Cost Breakdown</h5>
									<div class="space-y-1">
										{#each Object.entries(calculateReceiptCosts(receipt, receipt.people)) as [person, cost]}
											<div class="flex justify-between items-center text-xs">
												<div class="flex items-center space-x-1">
													<span class="font-medium text-xs bg-green-200 text-green-900 w-4 h-4 rounded-full flex items-center justify-center text-[10px]">
														{getInitials(person)}
													</span>
													<span class="text-gray-700">{person}:</span>
												</div>
												<span class="font-mono font-semibold text-gray-800">${cost.toFixed(2)}</span>
											</div>
										{/each}
										<div class="border-t border-green-200 pt-1 mt-1 flex justify-between items-center font-semibold text-xs">
											<span class="text-gray-800">Total:</span>
											<span class="font-mono text-green-700">
												${Object.values(calculateReceiptCosts(receipt, receipt.people)).reduce((a, b) => a + b, 0).toFixed(2)}
											</span>
										</div>
									</div>

									<!-- Payment Status -->
									{#if receipt.paid_by}
										<div class="mt-2 pt-2 border-t border-green-200">
											<p class="text-xs font-medium text-green-800 mb-1">Payments needed:</p>
											<div class="space-y-0.5">
												{#each Object.entries(calculateReceiptCosts(receipt, receipt.people)) as [person, owes]}
													{#if person !== receipt.paid_by && owes > 0}
														<div class="flex justify-between text-xs">
															<span class="text-gray-600">{person} → {receipt.paid_by}:</span>
															<span class="font-mono font-medium text-gray-800">${owes.toFixed(2)}</span>
														</div>
													{/if}
												{/each}
											</div>
										</div>
									{:else}
										<div class="mt-2 pt-2 border-t border-green-200">
											<p class="text-xs text-yellow-700">No payment recorded</p>
										</div>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- New Receipt Modal -->
	<NewReceiptModal 
		bind:show={showNewReceiptForm} 
		{group} 
		{loading}
		onSubmit={handleCreateReceipt}
	/>
</main>
