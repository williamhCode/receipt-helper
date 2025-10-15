import type { Receipt, Group } from './types';

// ============================================================================
// Constants
// ============================================================================

export const TAX_RATE = 0.07;

// ============================================================================
// Utility functions
// ============================================================================

export function getInitials(name: string): string {
	const parts = name.trim().split(/\s+/);
	if (parts.length === 1) {
		return parts[0].charAt(0).toUpperCase();
	}
	return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

// ============================================================================
// Calculation functions
// ============================================================================

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

	return costs;
}
