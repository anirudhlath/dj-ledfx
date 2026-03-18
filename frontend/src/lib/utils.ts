import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

export type { WithElementRef } from 'bits-ui';
export type { WithoutChild, WithoutChildrenOrChild } from 'svelte-toolbelt';

// Alias needed by some shadcn-svelte generated components (e.g. skeleton)
export type WithoutChildren<T> = Omit<T, 'children'>;
