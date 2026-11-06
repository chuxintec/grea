'use strict';
// One UTF-16 -> UTF-8 index, avoiding repeated whole-prefix scans on large bundles.
module.exports = function offsets(source) {
  const out=new Uint32Array(source.length+1);let bytes=0;
  for(let i=0;i<source.length;i++){
    out[i]=bytes;const c=source.charCodeAt(i);
    if(c>=0xd800&&c<=0xdbff&&i+1<source.length&&source.charCodeAt(i+1)>=0xdc00&&source.charCodeAt(i+1)<=0xdfff){out[++i]=bytes;bytes+=4;}
    else bytes+=c<0x80?1:c<0x800?2:3;
  }
  out[source.length]=bytes;return out;
};
