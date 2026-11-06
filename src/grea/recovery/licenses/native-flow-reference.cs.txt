/*
Cocos engine v3.8.7 Layout geometry reference
Copyright (c) 2013-2016 Chukong Technologies Inc.
 Copyright (c) 2017-2023 Xiamen Yaji Software Co., Ltd.

 http://www.cocos.com

 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights to
 use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
 of the Software, and to permit persons to whom the Software is furnished to do so,
 subject to the following conditions:

 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 THE SOFTWARE.
*/
using System.Collections.Generic;
using UnityEngine;

// Native uGUI flow layout with scaled child bounds, fixed rows/columns and
// cell-driven child sizing. No source IDs, serialized graph or interpreter.
[AddComponentMenu("Layout/Native Flow Layout Group")]
public sealed class NativeFlowLayoutGroup : NativeChildLayoutGroup
{
    public int Axis,FixedRows,FixedColumns;
    public bool ReverseHorizontal,ReverseVertical,IncludeScale,ResizeContainer,ResizeChildren;
    public Vector2 CellSize,Spacing;
    public override int layoutPriority { get { return 1; } }
    float Scale(RectTransform child,int axis){return IncludeScale?Mathf.Abs(child.localScale[axis]):1;}
    float Extent(RectTransform child,int axis){return child.rect.size[axis]*Scale(child,axis);}
    float Before(int axis){return axis==0?padding.left:padding.bottom;}
    float After(int axis){return axis==0?padding.right:padding.top;}
    int Limit(){int count=rectChildren.Count;return Axis==0?(FixedColumns>0?FixedColumns:FixedRows>0?Mathf.CeilToInt((float)count/FixedRows):0):(FixedRows>0?FixedRows:FixedColumns>0?Mathf.CeilToInt((float)count/FixedColumns):0);}
    List<List<RectTransform>> Lines(){
        var result=new List<List<RectTransform>>();var line=new List<RectTransform>();float used=0,available=rectTransform.rect.size[Axis]-Before(Axis)-After(Axis);int limit=Limit();
        foreach(var child in rectChildren){
            if(ResizeChildren)for(int a=0;a<2;a++){float scale=Scale(child,a);if(scale>0)child.SetSizeWithCurrentAnchors((RectTransform.Axis)a,CellSize[a]/scale);}
            float extent=Extent(child,Axis);
            if(line.Count>0&&(limit>0?line.Count>=limit:used+Spacing[Axis]+extent>available+.0001f)){result.Add(line);line=new List<RectTransform>();used=0;}
            used+=(line.Count>0?Spacing[Axis]:0)+extent;line.Add(child);
        }
        if(line.Count>0)result.Add(line);return result;
    }
    List<float> Offsets(List<List<RectTransform>> lines,out float extent){
        int cross=1-Axis;float row=0,temporary=0,previousMaximum=0,total=0;var offsets=new List<float>();
        for(int lineIndex=0;lineIndex<lines.Count;lineIndex++){
            foreach(var child in lines[lineIndex]){
                float next=Extent(child,cross);
                if(next>temporary){previousMaximum=Mathf.Max(temporary,previousMaximum);row=temporary!=0?temporary:next;temporary=next;}
                if(child==lines[lineIndex][0]){
                    if(lineIndex>0){
                        if(Limit()>0)row=temporary>(Axis==0?next:Extent(child,Axis))?temporary:row;
                        if(next!=temporary)row=temporary;
                        total+=row+Spacing[cross];row=temporary=next;
                    }
                    offsets.Add(total);
                }
            }
        }
        extent=Mathf.Max(previousMaximum,total+Mathf.Max(row,temporary))+Before(cross)+After(cross);return offsets;
    }
    float Preferred(){float extent;Offsets(Lines(),out extent);return extent;}
    public override void CalculateLayoutInputHorizontal(){
        foreach(Transform t in transform){var child=t as RectTransform;if(child==null)continue;var local=child.localPosition;child.anchorMin=child.anchorMax=rectTransform.pivot;child.localPosition=local;}
        base.CalculateLayoutInputHorizontal();float size=ResizeContainer&&Axis==1?Preferred():rectTransform.rect.width;SetLayoutInputForAxis(size,float.PositiveInfinity,size,-1,0);}
    public override void CalculateLayoutInputVertical(){float size=ResizeContainer&&Axis==0?Preferred():rectTransform.rect.height;SetLayoutInputForAxis(size,float.PositiveInfinity,size,-1,1);}
    public override void SetLayoutHorizontal(){if(Axis==1)Arrange();}
    public override void SetLayoutVertical(){if(Axis==0)Arrange();}
    void Arrange(){
        int cross=1-Axis;bool reverse=Axis==0?ReverseHorizontal:ReverseVertical,reverseCross=Axis==0?ReverseVertical:ReverseHorizontal;
        var lines=Lines();float unused;var offsets=Offsets(lines,out unused);int lineIndex=0;
        foreach(var line in lines){float max=0;float cursor=(reverse?1-rectTransform.pivot[Axis]:-rectTransform.pivot[Axis])*rectTransform.rect.size[Axis]+(reverse?-After(Axis):Before(Axis));
            foreach(var child in line){float extent=Extent(child,Axis),other=Extent(child,cross);max=Mathf.Max(max,other);
                var local=child.localPosition;local[Axis]=cursor+(reverse?-(1-child.pivot[Axis]):child.pivot[Axis])*extent;
                float boundary=(reverseCross?1-rectTransform.pivot[cross]:-rectTransform.pivot[cross])*rectTransform.rect.size[cross];
                local[cross]=boundary+(reverseCross?-1:1)*(offsets[lineIndex]+(1-child.pivot[cross])*other+(reverseCross?After(cross):Before(cross)));
                child.localPosition=local;cursor+=(reverse?-1:1)*(extent+Spacing[Axis]);
            }
            lineIndex++;
        }
    }
}
