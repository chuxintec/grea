export class PureSequence {
    static requireFinite(value: number, location: string): number {
        if (!Number.isFinite(value)) throw new Error("Non-finite Number at " + location + ".");
        return value;
    }

    static filter<T>(items: ReadonlyArray<T>, predicate: (item: T) => boolean): Array<T> {
        if (!items) throw new Error("Array.filter input is missing.");
        if (!predicate) throw new Error("Array.filter predicate is missing.");
        const result: Array<T> = [];
        for (const item of items) if (predicate(item)) result.push(item);
        return result;
    }

    static stableSort<T>(items: ReadonlyArray<T>, compare: (left: T, right: T) => number): Array<T> {
        if (!items) throw new Error("Array.sort input is missing.");
        if (!compare) throw new Error("Array.sort comparator is missing.");
        const result = Array.from(items);
        for (let i = 1; i < result.length; i++) {
            const value = result[i];
            let cursor = i - 1;
            while (cursor >= 0) {
                const order = PureSequence.requireFinite(compare(result[cursor], value), "sort comparator");
                if (order <= 0) break;
                result[cursor + 1] = result[cursor];
                cursor--;
            }
            result[cursor + 1] = value;
        }
        return result;
    }
}
