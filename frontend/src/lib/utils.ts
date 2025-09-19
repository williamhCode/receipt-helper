// Types
export interface ReceiptEntry {
	id: number;
	name: string;
	price: number;
	taxable: boolean;
	assigned_to: string[];
	receipt_id: number;
}

export interface Receipt {
	id: number;
	created_at: string;
	processed: boolean;
	name: string; // Required receipt name
	raw_data: string | null; // Optional raw receipt data
	paid_by: string | null;
	group_id: number;
	people: string[]; // Receipt-specific people list
	entries: ReceiptEntry[];
}

export interface Group {
	id: number;
	created_at: string;
	slug: string;
	people: string[];
	receipts: Receipt[];
}

// Constants
export const API_BASE = 'http://localhost:8000';
export const TAX_RATE = 0.07;

// Utility functions
export function handleError(err: unknown, context: string): string {
	console.error(`Error in ${context}:`, err);
	
	if (err instanceof TypeError && err.message.includes('fetch')) {
		return `Network Error: Failed to connect to ${API_BASE}.`;
	}
	
	if (err instanceof Error) {
		if (err.message.includes('HTTP')) {
			return err.message;
		}
		return `${context}: ${err.message}`;
	}
	
	return `${context}: Unknown error occurred`;
}

export function getInitials(name: string): string {
	const parts = name.trim().split(/\s+/);
	if (parts.length === 1) {
		return parts[0].charAt(0).toUpperCase();
	}
	return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

export function calculateReceiptTotal(receipt: Receipt): number {
	return receipt.entries.reduce((total, entry) => {
		const price = entry.taxable ? entry.price * (1 + TAX_RATE) : entry.price;
		return total + price;
	}, 0);
}

export function calculateReceiptCosts(receipt: Receipt, people: string[]): Record<string, number> {
	const costs: Record<string, number> = {};
	people.forEach(person => costs[person] = 0);

	receipt.entries.forEach(entry => {
		const assignedCount = entry.assigned_to.length;
		const price = entry.taxable ? entry.price * (1 + TAX_RATE) : entry.price;
		
		if (assignedCount === 0) {
			const pricePerPerson = price / people.length;
			people.forEach(person => costs[person] += pricePerPerson);
		} else {
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

export function calculateCombinedCosts(group: Group): Record<string, number> {
	const costs: Record<string, number> = {};
	group.people.forEach(person => costs[person] = 0);

	// Calculate what each person owes for items
	group.receipts.forEach(receipt => {
    if (receipt.processed) return;

		const receiptCosts = calculateReceiptCosts(receipt, receipt.people);
		receipt.people.forEach(person => {
			costs[person] += receiptCosts[person];
		});

		if (receipt.paid_by && costs[receipt.paid_by] !== undefined) {
			costs[receipt.paid_by] -= calculateReceiptTotal(receipt);
		}
	});

	// Subtract what each person paid
	group.receipts.forEach(receipt => {
	});

	return costs;
}

export function getUnprocessedReceiptsTotal(group: Group): number {
	return group.receipts
		.filter(receipt => !receipt.processed)
		.reduce((total, receipt) => total + calculateReceiptTotal(receipt), 0);
}

// API functions
export async function fetchGroups() {
	const response = await fetch(`${API_BASE}/groups/`);
	
	if (!response.ok) {
		const errorText = await response.text().catch(() => 'Unknown server error');
		throw new Error(`HTTP ${response.status} (${response.statusText}): ${errorText}`);
	}
	
	return await response.json() as Group[];
}

export async function fetchGroup(groupId: number) {
	const response = await fetch(`${API_BASE}/groups/${groupId}`);
	
	if (!response.ok) {
		const errorText = await response.text().catch(() => 'Unknown server error');
		throw new Error(`HTTP ${response.status} (${response.statusText}): ${errorText}`);
	}
	
	return await response.json() as Group;
}

export async function createSampleData() {
	const response = await fetch(`${API_BASE}/create-sample-data`, { method: 'POST' });
	
	if (!response.ok) {
		const errorText = await response.text().catch(() => 'Unknown server error');
		throw new Error(`HTTP ${response.status} (${response.statusText}): ${errorText}`);
	}
	
	return await response.json();
}

export async function createReceipt(groupId: number, receiptData: {
	processed: boolean;
  name: string;
	raw_data: string | null;
	paid_by: string | null;
	people: string[];
	entries: any[];
}) {
	const response = await fetch(`${API_BASE}/groups/${groupId}/receipts/`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify(receiptData)
	});

	if (!response.ok) {
		const errorText = await response.text().catch(() => 'Unknown server error');
		throw new Error(`HTTP ${response.status} (${response.statusText}): ${errorText}`);
	}

	return await response.json() as Receipt;
}

export async function updateGroup(groupId: number, groupData: { people: string[] }) {
	const response = await fetch(`${API_BASE}/groups/${groupId}`, {
		method: 'PATCH',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify(groupData)
	});

	if (!response.ok) {
		const errorText = await response.text().catch(() => 'Unknown server error');
		throw new Error(`HTTP ${response.status} (${response.statusText}): ${errorText}`);
	}

	return await response.json() as Group;
}

export async function updateReceipt(receiptId: number, receiptData: { people?: string[]; processed?: boolean }) {
	const response = await fetch(`${API_BASE}/receipts/${receiptId}`, {
		method: 'PATCH',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify(receiptData)
	});

	if (!response.ok) {
		const errorText = await response.text().catch(() => 'Unknown server error');
		throw new Error(`HTTP ${response.status} (${response.statusText}): ${errorText}`);
	}

	return await response.json() as Receipt;
}
