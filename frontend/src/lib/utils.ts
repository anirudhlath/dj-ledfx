import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

export type { WithElementRef } from 'bits-ui';
export type { WithoutChild, WithoutChildrenOrChild } from 'svelte-toolbelt';
