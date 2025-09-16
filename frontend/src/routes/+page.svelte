<script lang="ts">
	import { onMount } from 'svelte';

	// Types
	interface ReceiptEntry {
		id: number;
		name: string;
		price: number;
		taxable: boolean;
		assigned_to: string[];
		receipt_id: number;
	}

	interface Receipt {
		id: number;
		created_at: string;
		processed: boolean;
		raw_data: string | null;
		group_id: number;
		entries: ReceiptEntry[];
	}

	interface Group {
		id: number;
		created_at: string;
		slug: string;
		people: string[];
		receipts: Receipt[];
	}

	// State
	let groups: Group[] = [];
	let selectedReceipt: Receipt | null = null;
	let loading = false;
	let error = '';

	const API_BASE = 'http://localhost:8000'; // Adjust if your FastAPI runs on different port

	function handleError(err: unknown, context: string): string {
		console.error(`Error in ${context}:`, err);
		
		if (err instanceof TypeError && err.message.includes('fetch')) {
			// Network errors (connection refused, etc.)
			return `Network Error: Failed to connect to ${API_BASE}.`;
		}
		
		if (err instanceof Error) {
			// Check if it's a fetch response error with additional info
			if (err.message.includes('HTTP')) {
				return err.message;
			}
			return `${context}: ${err.message}`;
		}
		
		return `${context}: Unknown error occurred`;
	}

	// Enhanced API Functions
	async function fetchGroups() {
		try {
			loading = true;
			error = ''; // Clear previous errors
			
			const response = await fetch(`${API_BASE}/groups/`);
			
			if (!response.ok) {
				const errorText = await response.text().catch(() => 'Unknown server error');
				throw new Error(`HTTP ${response.status} (${response.statusText}): ${errorText}`);
			}
			
			groups = await response.json();
		} catch (err) {
			error = handleError(err, 'Failed to fetch groups');
		} finally {
			loading = false;
		}
	}

	async function fetchReceipt(receiptId: number) {
		try {
			loading = true;
			error = ''; // Clear previous errors
			
			const response = await fetch(`${API_BASE}/receipts/${receiptId}`);
			
			if (!response.ok) {
				const errorText = await response.text().catch(() => 'Unknown server error');
				throw new Error(`HTTP ${response.status} (${response.statusText}): ${errorText}`);
			}
			
			selectedReceipt = await response.json();
		} catch (err) {
			error = handleError(err, `Failed to fetch receipt ${receiptId}`);
		} finally {
			loading = false;
		}
	}

	async function createSampleData() {
		try {
			loading = true;
			error = ''; // Clear previous errors
			
			const response = await fetch(`${API_BASE}/create-sample-data`, { method: 'POST' });
			
			if (!response.ok) {
				const errorText = await response.text().catch(() => 'Unknown server error');
				throw new Error(`HTTP ${response.status} (${response.statusText}): ${errorText}`);
			}
			
			await fetchGroups();
		} catch (err) {
			error = handleError(err, 'Failed to create sample data');
		} finally {
			loading = false;
		}
	}

	async function updateAssignment(entryId: number, person: string, assigned: boolean) {
		if (!selectedReceipt) return;

		// Update local state optimistically
		const entry = selectedReceipt.entries.find(e => e.id === entryId);
		if (entry) {
			if (assigned && !entry.assigned_to.includes(person)) {
				entry.assigned_to.push(person);
			} else if (!assigned) {
				entry.assigned_to = entry.assigned_to.filter(p => p !== person);
			}
		}

		// Force reactivity
		selectedReceipt = selectedReceipt;
	}

	function calculateCosts(receipt: Receipt, people: string[]): Record<string, number> {
		const costs: Record<string, number> = {};
		people.forEach(person => costs[person] = 0);

		const TAX_RATE = 0.07;

		receipt.entries.forEach(entry => {
			const assignedCount = entry.assigned_to.length;
			const price = entry.taxable ? entry.price * (1 + TAX_RATE) : entry.price;
			
			if (assignedCount === 0) {
				// Split among all people if no one is assigned
				const pricePerPerson = price / people.length;
				people.forEach(person => costs[person] += pricePerPerson);
			} else {
				// Split among assigned people
				const pricePerPerson = price / assignedCount;
				entry.assigned_to.forEach(person => {
					if (costs[person] !== undefined) {
						costs[person] += pricePerPerson;
					}
				});
			}
		});

		return costs;
	}

	onMount(() => {
		fetchGroups();
	});
</script>

<main class="container mx-auto p-6 bg-gray-50 min-h-screen">
	<h1 class="text-3xl font-bold mb-6 text-gray-800">Receipt Helper</h1>

	{#if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
			<div class="flex items-start">
				<div class="flex-shrink-0">
					<svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
						<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
					</svg>
				</div>
				<div class="ml-3 flex-1">
					<h3 class="text-sm font-medium text-red-800 mb-2">Error Details</h3>
					<div class="text-sm text-red-700">
						<p class="font-mono bg-red-100 p-2 rounded text-xs overflow-x-auto">{error}</p>
					</div>
					<div class="mt-3 text-xs text-red-600">
						<p><strong>API Endpoint:</strong> {API_BASE}</p>
						<p><strong>Timestamp:</strong> {new Date().toLocaleString()}</p>
					</div>
				</div>
				<div class="ml-auto pl-3">
					<button
						on:click={() => error = ''}
						class="inline-flex text-red-400 hover:text-red-600 focus:outline-none focus:text-red-600"
					>
						<svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
							<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
						</svg>
					</button>
				</div>
			</div>
		</div>
	{/if}

	{#if loading}
		<div class="text-center py-8">
			<div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
			<p class="mt-2 text-gray-600">Loading...</p>
		</div>
	{/if}

	<div class="grid md:grid-cols-2 gap-6">
		<!-- Groups Section -->
		<div class="bg-white p-6 rounded-lg shadow-md">
			<div class="flex justify-between items-center mb-4">
				<h2 class="text-xl font-semibold text-gray-700">Groups</h2>
				<button 
					on:click={createSampleData}
					class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:opacity-50 transition-colors"
					disabled={loading}
				>
					Create Sample Data
				</button>
			</div>

			{#if groups.length === 0 && !loading}
				<p class="text-gray-500">No groups found. Create some sample data to get started!</p>
			{:else}
				{#each groups as group}
					<div class="border border-gray-200 rounded-lg p-4 mb-4 hover:shadow-sm transition-shadow">
						<div class="flex justify-between items-start mb-2">
							<h3 class="font-medium text-gray-800">Group {group.id}</h3>
							<span class="text-sm text-gray-500 font-mono bg-gray-100 px-2 py-1 rounded">
								{group.slug}
							</span>
						</div>
						<p class="text-sm text-gray-600 mb-2">
							<span class="font-medium">People:</span> {group.people.join(', ')}
						</p>
						<p class="text-sm text-gray-600 mb-3">
							<span class="font-medium">Receipts:</span> {group.receipts.length}
						</p>
						
						{#if group.receipts.length > 0}
							<div class="space-y-2">
								<p class="text-sm font-medium text-gray-700">Select a receipt:</p>
								{#each group.receipts as receipt}
									<button
										on:click={() => fetchReceipt(receipt.id)}
										class="w-full text-left p-3 text-sm bg-gray-50 hover:bg-gray-100 rounded border transition-colors"
										class:bg-blue-50={selectedReceipt?.id === receipt.id}
										class:border-blue-200={selectedReceipt?.id === receipt.id}
									>
										<div class="flex justify-between items-center">
											<span class="font-medium">Receipt #{receipt.id}</span>
											<span class="text-gray-500">{receipt.entries.length} items</span>
										</div>
									</button>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			{/if}
		</div>

		<!-- Receipt Details Section -->
		<div class="bg-white p-6 rounded-lg shadow-md">
			<h2 class="text-xl font-semibold mb-4 text-gray-700">Receipt Details</h2>
			
			{#if selectedReceipt}
				<div class="mb-6">
					<h3 class="font-medium mb-2 text-gray-800">Receipt #{selectedReceipt.id}</h3>
					<p class="text-sm text-gray-600">
						Created: {new Date(selectedReceipt.created_at).toLocaleDateString()}
					</p>
				</div>

				<!-- Get the group for this receipt -->
				{#each groups as group}
					{#if group.receipts.some(r => r.id === selectedReceipt.id)}
						<!-- Items Table -->
						<div class="mb-6">
							<h4 class="font-medium mb-3 text-gray-700">Items</h4>
							<div class="overflow-x-auto border border-gray-200 rounded-lg">
								<table class="w-full text-sm">
									<thead class="bg-gray-50 border-b border-gray-200">
										<tr>
											<th class="p-3 text-left font-medium text-gray-700">Item</th>
											<th class="p-3 text-left font-medium text-gray-700">Price</th>
											<th class="p-3 text-center font-medium text-gray-700">Taxed</th>
											{#each group.people as person}
												<th class="p-3 text-center font-medium text-gray-700">{person}</th>
											{/each}
										</tr>
									</thead>
									<tbody>
										{#each selectedReceipt.entries as entry, i}
											<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors" class:bg-gray-25={i % 2 === 1}>
												<td class="p-3 text-gray-800">{entry.name}</td>
												<td class="p-3 text-gray-800 font-mono">${entry.price.toFixed(2)}</td>
												<td class="p-3 text-center">
													<span class="text-xs px-2 py-1 rounded-full" 
														  class:bg-green-100={entry.taxable}
														  class:text-green-800={entry.taxable}
														  class:bg-gray-100={!entry.taxable}
														  class:text-gray-600={!entry.taxable}>
														{entry.taxable ? 'Yes' : 'No'}
													</span>
												</td>
												{#each group.people as person}
													<td class="p-3 text-center">
														<input
															type="checkbox"
															checked={entry.assigned_to.includes(person)}
															on:change={(e) => updateAssignment(entry.id, person, e.currentTarget.checked)}
															class="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
														/>
													</td>
												{/each}
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						</div>

						<!-- Cost Breakdown -->
						<div class="bg-gradient-to-br from-blue-50 to-indigo-50 p-4 rounded-lg border border-blue-200">
							<h4 class="font-medium mb-3 text-gray-700">Cost Breakdown</h4>
							<div class="space-y-2">
								{#each Object.entries(calculateCosts(selectedReceipt, group.people)) as [person, cost]}
									<div class="flex justify-between items-center">
										<span class="text-gray-700">{person}:</span>
										<span class="font-mono font-semibold text-gray-800">${cost.toFixed(2)}</span>
									</div>
								{/each}
								<div class="border-t border-blue-200 mt-3 pt-3 flex justify-between items-center font-semibold text-lg">
									<span class="text-gray-800">Total:</span>
									<span class="font-mono text-blue-700">
										${Object.values(calculateCosts(selectedReceipt, group.people)).reduce((a, b) => a + b, 0).toFixed(2)}
									</span>
								</div>
							</div>
						</div>
					{/if}
				{/each}
			{:else}
				<div class="text-center py-12">
					<div class="text-gray-400 mb-2">
						<svg class="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
						</svg>
					</div>
					<p class="text-gray-500">Select a receipt to view details</p>
				</div>
			{/if}
		</div>
	</div>
</main>
