// Services-layer port adapter. Gameplay persists pending before send and retries the exact envelope.
export interface Command { operationId: string; expectedRevision: string; action: string; configVersion: string; }
export class CocosGateway {
    constructor(private base: string, private session: string) {}
    async command(value: Command, signal?: AbortSignal): Promise<unknown> {
        const response = await fetch(this.base + '/v1/command', { method: 'POST', headers: { 'Content-Type':'application/json', Authorization: 'Bearer ' + this.session }, body: JSON.stringify(value), signal });
        if (!response.ok) throw new Error('Result may be unknown; retain same operation ID and payload');
        return response.json(); // gRPC/HTTP success still requires code === APPLIED (or explicit refusal).
    }
}
