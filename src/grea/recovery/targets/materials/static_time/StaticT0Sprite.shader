Shader "Monkey/StaticTime/SourceSpriteT0"
{
    Properties
    {
        [PerRendererData] _MainTex ("Sprite Texture", 2D) = "white" {}
        _Color ("Vertex Tint", Color) = (1,1,1,1)
        _StaticSourceTimeSeconds ("Pinned Source Time", Float) = 0
        _SourceScalar0 ("Source Scalar 0", Float) = 0
        _SourceScalar1 ("Source Scalar 1", Float) = 0
        _SourceScalar2 ("Source Scalar 2", Float) = 0
        _SourceScalar3 ("Source Scalar 3", Float) = 0
        _SourceScalar4 ("Source Scalar 4", Float) = 0
        _SourceScalar5 ("Source Scalar 5", Float) = 0
        _SourceScalar6 ("Source Scalar 6", Float) = 0
        _SourceColor0 ("Source Color 0", Color) = (1,1,1,1)
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
            float _StaticSourceTimeSeconds;
            float _SourceScalar0;
            float _SourceScalar1;
            float _SourceScalar2;
            float _SourceScalar3;
            float _SourceScalar4;
            float _SourceScalar5;
            float _SourceScalar6;
            fixed4 _SourceColor0;

            // The t0 profile is deliberately independent of Unity/Cocos clocks.
            static const float MONKEY_STATIC_SOURCE_TIME_SECONDS = 0.0;

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

            fixed4 frag(v2f i) : SV_Target
            {
                fixed4 result = (tex2D(_MainTex, i.uv) + _TextureSampleAdd) * i.color;
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
