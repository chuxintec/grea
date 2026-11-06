Shader "Monkey/UnitySource/TextOutline" {
 Properties {
  [PerRendererData] _MainTex ("Font",2D)="white"{}
  _StencilComp ("Stencil comparison",Float)=8
  _Stencil ("Stencil reference",Float)=0
  _StencilOp ("Stencil pass",Float)=0
  _StencilWriteMask ("Stencil write",Float)=255
  _StencilReadMask ("Stencil read",Float)=255
  _ColorMask ("Color mask",Float)=15
  [Toggle(UNITY_UI_ALPHACLIP)] _UseUIAlphaClip ("Alpha clip",Float)=0
 }
 SubShader {
  Tags {"Queue"="Transparent" "RenderType"="Transparent" "IgnoreProjector"="True"}
  Stencil {Ref [_Stencil] Comp [_StencilComp] Pass [_StencilOp] ReadMask [_StencilReadMask] WriteMask [_StencilWriteMask]}
  Cull Off ZWrite Off ZTest [unity_GUIZTestMode] Blend SrcAlpha OneMinusSrcAlpha ColorMask [_ColorMask]
  Pass {
   CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #pragma multi_compile_local _ UNITY_UI_CLIP_RECT
   #pragma multi_compile_local _ UNITY_UI_ALPHACLIP
   #include "UnityCG.cginc"
   #include "UnityUI.cginc"
   struct Input { float4 pos:POSITION; float4 color:COLOR; float2 uv:TEXCOORD0; float2 lo:TEXCOORD1; float4 hiStep:TEXCOORD2; float4 stroke:TEXCOORD3; };
   struct Varying {float4 pos:SV_POSITION; float4 color:COLOR; float2 uv:TEXCOORD0; float2 lo:TEXCOORD1; float4 hiStep:TEXCOORD2; float4 stroke:TEXCOORD3; float2 local:TEXCOORD4;};
   sampler2D _MainTex; float4 _TextureSampleAdd, _ClipRect;
   Varying vert(Input v){Varying o;o.pos=UnityObjectToClipPos(v.pos);o.local=v.pos.xy;o.color=v.color;o.uv=v.uv;o.lo=v.lo;o.hiStep=v.hiStep;o.stroke=v.stroke;return o;}
   float insideGlyph(float2 uv,Varying i){return all(uv>=i.lo)&&all(uv<=i.hiStep.xy);}
   fixed4 frag(Varying i):SV_Target{
    float4 face=(tex2D(_MainTex,i.uv)+_TextureSampleAdd)*i.color;
    if(i.stroke.w>0){
     float a=face.a*insideGlyph(i.uv,i), ring=0;
     [unroll] for(int n=0;n<12;n++){
      float angle=n*0.5235987756;float2 uv=i.uv+float2(cos(angle),sin(angle))*i.hiStep.zw*i.stroke.w;
      ring+=insideGlyph(uv,i)*(tex2D(_MainTex,uv).a+_TextureSampleAdd.a);
     }
     face=float4(face.rgb*a+i.stroke.rgb*(1-a),max(a,saturate(ring))*i.color.a);
    }
    #ifdef UNITY_UI_CLIP_RECT
     face.a*=UnityGet2DClipping(i.local,_ClipRect);
    #endif
    #ifdef UNITY_UI_ALPHACLIP
     clip(face.a-0.001);
    #endif
    return face;
   }
   ENDCG
  }
 }
}
