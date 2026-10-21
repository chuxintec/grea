export interface Snapshot { value: number; }
export function readConfig(value: unknown): number {
    const v = value as { step?: unknown };
    if (!v || !Number.isSafeInteger(v.step) || Number(v.step) <= 0) throw new Error('Invalid counter JSON');
    return Number(v.step);
}
