import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function sliderValue(v: number | readonly number[]): number {
  if (typeof v === "number") return v
  return v[0]
}
