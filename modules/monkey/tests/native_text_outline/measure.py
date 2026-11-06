from pathlib import Path
import json,sys,hashlib
from PIL import Image,ImageChops
capture=Path(sys.argv[1]).resolve();w=Path(sys.argv[2]).resolve()
cases=json.loads((w/'cases.json').read_bytes());rows=[];errors=[];bg=(255,226,165);face=(193,121,47);white=(255,255,255)
def rgb(tag,name):return Image.open(capture/tag/(name+'.png')).convert('RGB')
def same(a,b):return ImageChops.difference(a,b).getbbox() is None
def dot(a,b):return sum(x*y for x,y in zip(a,b))
u=[x-y for x,y in zip(face,bg)];v=[x-y for x,y in zip(white,bg)];aa=dot(u,u);bb=dot(v,v);ab=dot(u,v);det=aa*bb-ab*ab
def bounds(im):
 data=[];stroke=0.;base=list(im.getdata())
 for px in base:
  z=[x-y for x,y in zip(px,bg)];f=(bb*dot(u,z)-ab*dot(v,z))/det;s=(aa*dot(v,z)-ab*dot(u,z))/det
  data.append(min(1,max(0.,f)+max(0.,s)));stroke+=max(0.,s)
 width,height=im.size
 def start(seq):
  i=next(i for i,x in enumerate(seq) if x>=.5)
  assert i>1 and i<len(seq)-1,'clipped label in measuring viewport'
  return i-1+(.5-seq[i-1])/(seq[i]-seq[i-1])
 x=[max(data[i::width]) for i in range(width)];y=[max(data[i*width:(i+1)*width]) for i in range(height)]
 return [start(x),width-1-start(x[::-1]),start(y),height-1-start(y[::-1])],stroke
for c in cases:
 n=c['name'];group,_,mode=n.rpartition('-');mode=mode or n
 baseline=(group+'-' if group else '')+'plain'
 get=lambda k:json.loads((capture/'cold'/(k+'.json')).read_bytes())
 draw=get(n);ref=get(baseline)
 ctl=rgb('cold',baseline);im=rgb('cold',n)
 base,offstroke=bounds(ctl);extent,stroke=bounds(im)
 edges=[round((e-b)*q,3) for e,b,q in zip(extent,base,[-1,1,-1,1])]
 a=rgb('cold',baseline+'-white');b=rgb('cold',n+'-white')
 d=ImageChops.difference(a,b);neutral=sum(any(px) for px in d.getdata())
 maskDelta=sum((a[2]<151)!=(b[2]<151) for a,b in zip(a.getdata(),b.getdata()))
 cold=all(same(rgb('initial',n+k),rgb('cold',n+k)) for k in ['', '-white'])
 glyphs=draw['glyphFonts']==ref['glyphFonts'] and draw['glyphSlots']==ref['glyphSlots'] and draw['left']==ref['left'] and draw['right']==ref['right'] and draw['style']==ref['style'] and draw['size']==ref['size'] and all(s['atlasMatches'] for s in draw['slots'])
 expected=c['width'] if c['enabled'] and c['alpha']==255 and c['width'] else 0.
 edgeOK= max(abs(x-expected) for x in edges)<=1 if mode!='half' else True
 plainOK=same(ctl,im) if mode in ('disabled','zero','clear') else True
 row=dict(mode=n,sourceWidth=c['width'],sourceAlpha=c['alpha'],edgesLRTB=edges,neutralChangedPixels=neutral,neutralMaskChanges=maskDelta,neutralMaxChannelDelta=max(max(x) for x in d.getdata()),coldPixelExact=cold,sameGlyphsMetrics=glyphs,identicalToPlain=same(ctl,im),visibleStrokeCoverage=round(stroke,3),driver=draw['driver'],tmpLayers=draw['textLayers'],slots=draw['slots'])
 rows.append(row)
 if not(cold and glyphs and edgeOK and plainOK and neutral==0):errors.append(n)
by={r['mode']:r for r in rows};den=by['w30']['visibleStrokeCoverage']-by['plain']['visibleStrokeCoverage']
alphaRatio=(by['half']['visibleStrokeCoverage']-by['plain']['visibleStrokeCoverage'])/den if den else None
if alphaRatio is None or abs(alphaRatio-128/255)>.08:errors.append('outline alpha')
report=dict(pixelTolerance=1,neutralBackground='white; exact RGB equality required',halfAlphaRatio=alphaRatio,rows=rows,failures=errors,passAll=not errors)
(capture/'measurements.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print([(r['mode'],r['edgesLRTB'],r['neutralChangedPixels'],r['coldPixelExact']) for r in rows]);print('failures',errors,'alpha',alphaRatio)

raise SystemExit(0 if report["passAll"] else 1)
