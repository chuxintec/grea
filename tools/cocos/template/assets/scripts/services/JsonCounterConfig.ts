import { JsonAsset, resources } from 'cc';
import { CounterConfig } from '../gameplay/CounterSession';
import { readConfig } from '../domain/Counter';
export class JsonCounterConfig implements CounterConfig {
    async load(): Promise<number> {
        const asset = await new Promise<JsonAsset>((resolve, reject) => resources.load('config/counter', JsonAsset, (error, result) => error ? reject(error) : resolve(result)));
        try { return readConfig(asset.json); } finally { resources.release('config/counter', JsonAsset); }
    }
}
