Shader "Monkey/Recovered/Shader2DOutline"
{
    Properties
    {
        [PerRendererData] _MainTex ("Sprite Texture", 2D) = "white" {}
        _Color ("Vertex Tint", Color) = (1,1,1,1)
        _OutlineColor ("Outline Color", Color) = (1,1,1,1)
        _OutlineTextureSize ("Outline Source Texture Size", Vector) = (128,128,0,0)
        _OutlineWidth ("Outline Width", Float) = 3
        _FillAlpha ("Fill Alpha", Float) = 0
        _AlphaThreshold ("Alpha Threshold", Float) = 0.01
        [HideInInspector] _StencilComp ("Stencil Comparison", Float) = 8
        [HideInInspector] _Stencil ("Stencil ID", Float) = 0
        [HideInInspector] _StencilOp ("Stencil Operation", Float) = 0
        [HideInInspector] _StencilWriteMask ("Stencil Write Mask", Float) = 255
        [HideInInspector] _StencilReadMask ("Stencil Read Mask", Float) = 255
        [HideInInspector] _ColorMask ("Color Mask", Float) = 15
        [HideInInspector] _UseUIAlphaClip ("Use UI Alpha Clip", Float) = 0
    }
    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" "IgnoreProjector"="True" "CanUseSpriteAtlas"="True" }
        Cull Off
        Lighting Off
        ZWrite Off
        ZTest [unity_GUIZTestMode]
        Blend SrcAlpha OneMinusSrcAlpha
        Stencil
        {
            Ref [_Stencil]
            Comp [_StencilComp]
            Pass [_StencilOp]
            ReadMask [_StencilReadMask]
            WriteMask [_StencilWriteMask]
        }
        ColorMask [_ColorMask]
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_local _ UNITY_UI_CLIP_RECT
            #pragma multi_compile_local _ UNITY_UI_ALPHACLIP
            #include "UnityCG.cginc"
            #include "UnityUI.cginc"
            float4 _ClipRect;

            sampler2D _MainTex;
            float4 _MainTex_ST;
            fixed4 _TextureSampleAdd;
            fixed4 _Color;
            fixed4 _OutlineColor;
            float2 _OutlineTextureSize;
            float _OutlineWidth;
            float _FillAlpha;
            float _AlphaThreshold;

            struct appdata
            {
                float4 vertex : POSITION;
                fixed4 color : COLOR;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                float4 worldPosition : TEXCOORD1;
                fixed4 color : COLOR;
                float2 uv : TEXCOORD0;
            };

            v2f vert(appdata v)
            {
                v2f o;
                o.worldPosition = v.vertex;
                o.vertex = UnityObjectToClipPos(o.worldPosition);
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                o.color = v.color * _Color;
                return o;
            }

            float sampleAlpha(float2 uv)
            {
                return (tex2D(_MainTex, uv) + _TextureSampleAdd).a;
            }

            float sampleRingAlpha(float2 uv, float2 stepUv, float radius)
            {
                float2 offset = stepUv * radius;
                float2 diag = offset * 0.70710678;
                float alpha = 0.0;
                alpha = max(alpha, sampleAlpha(uv + float2( offset.x, 0.0)));
                alpha = max(alpha, sampleAlpha(uv + float2(-offset.x, 0.0)));
                alpha = max(alpha, sampleAlpha(uv + float2(0.0,  offset.y)));
                alpha = max(alpha, sampleAlpha(uv + float2(0.0, -offset.y)));
                alpha = max(alpha, sampleAlpha(uv + float2( diag.x,  diag.y)));
                alpha = max(alpha, sampleAlpha(uv + float2(-diag.x,  diag.y)));
                alpha = max(alpha, sampleAlpha(uv + float2( diag.x, -diag.y)));
                alpha = max(alpha, sampleAlpha(uv + float2(-diag.x, -diag.y)));
                return alpha;
            }

            float getOutlineMask(float2 uv)
            {
                float2 safeTextureSize = max(_OutlineTextureSize, float2(1.0, 1.0));
                float2 stepUv = 1.0 / safeTextureSize;
                float width = clamp(_OutlineWidth, 0.0, 8.0);
                float sourceAlpha = sampleAlpha(uv);
                float neighborAlpha = 0.0;
                [unroll]
                for (int i = 1; i <= 8; i++)
                {
                    float ring = (float)i;
                    float ringWeight = clamp(width - ring + 1.0, 0.0, 1.0);
                    neighborAlpha = max(neighborAlpha, sampleRingAlpha(uv, stepUv, ring) * ringWeight);
                }
                float sourceMask = smoothstep(_AlphaThreshold, _AlphaThreshold + 0.05, sourceAlpha);
                float solidMask = smoothstep(0.45, 0.9, sourceAlpha);
                float neighborMask = smoothstep(_AlphaThreshold, _AlphaThreshold + 0.05, neighborAlpha);
                float softEdgeMask = sourceMask * (1.0 - solidMask);
                return max(max(neighborMask - solidMask, 0.0), softEdgeMask);
            }

            fixed4 frag(v2f i) : SV_Target
            {
                fixed4 sampled = tex2D(_MainTex, i.uv) + _TextureSampleAdd;
                fixed4 o = sampled;
                o *= i.color;
                float outlineMask = getOutlineMask(i.uv);
                float4 outline = float4(_OutlineColor.rgb, _OutlineColor.a * outlineMask);
                float sourceMask = smoothstep(_AlphaThreshold, _AlphaThreshold + 0.05, o.a);
                float4 source = float4(o.rgb, o.a * clamp(_FillAlpha, 0.0, 1.0) * sourceMask);
                float sourceBlend = sourceMask * clamp(_FillAlpha, 0.0, 1.0);
                float4 result = float4(lerp(outline.rgb, source.rgb, sourceBlend), max(outline.a, source.a));
                #ifdef UNITY_UI_CLIP_RECT
                    result.a *= UnityGet2DClipping(i.worldPosition.xy, _ClipRect);
                #endif
                #ifdef UNITY_UI_ALPHACLIP
                    clip(result.a - 0.001);
                #endif
                return result;
            }
            ENDCG
        }
    }
}
