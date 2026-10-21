import { Snapshot } from '../domain/Counter';
export interface CounterConfig { load(): Promise<number>; }
export class CounterSession {
    private value = 0;
    private alive = true;
    constructor(private step: number) {}
    snapshot(): Snapshot { return { value: this.value }; }
    press(): Snapshot { if (!this.alive) throw new Error('Disposed'); this.value += this.step; return this.snapshot(); }
    dispose() { this.alive = false; }
}
