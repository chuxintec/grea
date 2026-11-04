Shader "Monkey/Recovered/Shader2DUIColor"
{
    Properties
    {
        [PerRendererData] _MainTex ("Sprite Texture", 2D) = "white" {}
        _Color ("Vertex Tint", Color) = (1,1,1,1)
        _Brightness ("Brightness", Float) = 1
        _Saturation ("Saturation", Float) = 1
        _Constrast ("Constrast", Float) = 1
        _Gray ("Gray", Float) = 0
        _Silhouette ("Silhouette", Color) = (1,1,1,1)
        [HideInInspector] _StencilComp ("Stencil Comparison", Float) = 8
        [HideInInspector] _Stencil ("Stencil ID", Float) = 0
        [HideInInspector] _StencilOp ("Stencil Operation", Float) = 0
        [HideInInspector] _StencilWriteMask ("Stencil Write Mask", Float) = 255
        [HideInInspector] _StencilReadMask ("Stencil Read Mask", Float) = 255
        [HideInInspector] _ColorMask ("Color Mask", Float) = 15
        [HideInInspector] _UseUIAlphaClip ("Use Alpha Clip", Float) = 0
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
            float _Brightness;
            float _Saturation;
            float _Constrast;
            float _Gray;
            fixed4 _Silhouette;

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

            float3 lerp3(float3 a, float3 b, float w) { return a + w * (b - a); }

            fixed4 frag(v2f i) : SV_Target
            {
                fixed4 o = tex2D(_MainTex, i.uv) + _TextureSampleAdd;
                if (_Silhouette.r * _Silhouette.g * _Silhouette.b * _Silhouette.a != 1.0)
                    o = fixed4(_Silhouette.rgb, o.a * _Silhouette.a);
                if (_Gray > 0.0)
                {
                    float grayValue = dot(o.rgb, float3(0.2126, 0.7152, 0.0722));
                    grayValue *= 1.0 - _Gray;
                    o.rgb = grayValue.xxx;
                }
                float3 finalColor = o.rgb;
                if (_Brightness != 1.0) finalColor *= _Brightness;
                if (_Saturation != 1.0)
                {
                    float luminance = dot(o.rgb, float3(0.2125, 0.7154, 0.0721));
                    finalColor = lerp3(luminance.xxx, finalColor, _Saturation);
                }
                if (_Constrast != 1.0) finalColor = lerp3(float3(0.5, 0.5, 0.5), finalColor, _Constrast);
                o.rgb = finalColor;
                o *= i.color;
                #ifdef UNITY_UI_CLIP_RECT
                    o.a *= UnityGet2DClipping(i.worldPosition.xy, _ClipRect);
                #endif
                #ifdef UNITY_UI_ALPHACLIP
                    clip(o.a - 0.001);
                #endif
                return o;
            }
            ENDCG
        }
    }
}
