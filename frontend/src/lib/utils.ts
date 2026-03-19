import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function sliderValue(v: number | readonly number[]): number {
  return Array.isArray(v) ? v[0] : v
}
