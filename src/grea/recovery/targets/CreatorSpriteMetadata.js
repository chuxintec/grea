'use strict';
// Editor import metadata for the supported rectangular SpriteFrame profile.
// Shape matches Creator 3.8.8's native RECT mesh; never omit required vertices
// while changing trim metadata (the importer otherwise retains stale library data).
function rectVertices(asset){
    const [w,h]=asset.size,[tw,th]=asset.originalSize,[x,y]=asset.trimOrigin||[0,0];
    if(![w,h,tw,th,x,y].every(Number.isFinite)||w<=0||h<=0||tw<=0||th<=0||x<0||y<0||x+w>tw||y+h>th)throw Error('Invalid native SpriteFrame rectangle');
    const corners=[[-w/2,-h/2],[w/2,-h/2],[-w/2,h/2],[w/2,h/2]],rawPosition=corners.flatMap(p=>[...p,0]);
    const uv=[x,th-y,x+w,th-y,x,th-y-h,x+w,th-y-h];
    const nuv=[x/tw,(th-y-h)/th,(x+w)/tw,(th-y-h)/th,x/tw,(th-y)/th,(x+w)/tw,(th-y)/th];
    return {rawPosition,indexes:[0,1,2,2,1,3],uv,nuv,minPos:[-w/2,-h/2,0],maxPos:[w/2,h/2,0]};
}
function libraryMatches(asset,document){
    if(!document||document.__type__!=='cc.SpriteFrame'||!document.content)return false;
    const c=document.content,[x,y]=asset.trimOrigin||[0,0],[w,h]=asset.size;
    return c.rect&&c.rect.x===x&&c.rect.y===y&&c.rect.width===w&&c.rect.height===h&&
        c.originalSize&&c.originalSize.width===asset.originalSize[0]&&c.originalSize.height===asset.originalSize[1]&&
        c.offset&&c.offset.x===asset.offset[0]&&c.offset.y===asset.offset[1]&&
        Array.isArray(c.capInsets)&&c.capInsets.length===4&&c.capInsets.every((v,i)=>v===asset.border[i]);
}
module.exports={rectVertices,libraryMatches};
