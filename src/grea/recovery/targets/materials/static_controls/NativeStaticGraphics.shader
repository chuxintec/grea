Shader "Monkey/StaticControls/CocosBuiltin2DGraphics"
{
    Properties
    {
        [HideInInspector] _StencilComp ("Stencil Comparison", Float) = 8
        [HideInInspector] _Stencil ("Stencil ID", Float) = 0
        [HideInInspector] _StencilOp ("Stencil Operation", Float) = 0
        [HideInInspector] _StencilWriteMask ("Stencil Write Mask", Float) = 255
        [HideInInspector] _StencilReadMask ("Stencil Read Mask", Float) = 255
        [HideInInspector] _ColorMask ("Color Mask", Float) = 15
        [HideInInspector] _UseUIAlphaClip ("Use UI Alpha Clip", Float) = 0
        _AlphaThreshold ("Source Alpha Threshold", Float) = 0.5
    }
    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" "IgnoreProjector"="True" "CanUseSpriteAtlas"="True" }
        Cull Off
        Lighting Off
        ZWrite Off
        ZTest [unity_GUIZTestMode]
        Blend One OneMinusSrcAlpha
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
            #pragma target 3.0
            #pragma multi_compile_local _ UNITY_UI_CLIP_RECT
            #pragma multi_compile_local _ UNITY_UI_ALPHACLIP
            #include "UnityCG.cginc"
            #include "UnityUI.cginc"

            float4 _ClipRect;
            float _AlphaThreshold;

            struct appdata
            {
                float4 vertex : POSITION;
                fixed4 color : COLOR;
                float sourceDistance : TEXCOORD1;
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                float4 worldPosition : TEXCOORD0;
                fixed4 color : COLOR;
                float sourceDistance : TEXCOORD1;
            };

            v2f vert(appdata v)
            {
                v2f o;
                o.worldPosition = v.vertex;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.color = v.color;
                o.sourceDistance = v.sourceDistance;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                fixed4 result = i.color;
                #if defined(USE_ALPHA_TEST)
                    clip(result.a - _AlphaThreshold);
                #endif
                float aa = max(fwidth(i.sourceDistance), 0.05);
                float alpha = 1.0 - smoothstep(-aa, 0.0, abs(i.sourceDistance) - 1.0);
                result.rgb *= result.a;
                result *= alpha;
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
