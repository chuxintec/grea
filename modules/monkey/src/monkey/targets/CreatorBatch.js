'use strict';
// Independent assets only. Preserve input order and drain in-flight work on error.
async function map(items,limit,work) {
    if(!Number.isSafeInteger(limit)||limit<1)throw Error('Invalid batch limit');
    const result=new Array(items.length);let next=0,error,failed=false;
    async function worker() {
        while(!failed&&next<items.length) {
            const index=next++;
            try {result[index]=await work(items[index],index);}
            catch(e){if(!failed){failed=true;error=e;}}
        }
    }
    await Promise.all(Array.from({length:Math.min(limit,items.length)},worker));
    if(failed)throw error;
    return result;
}
module.exports={map};
