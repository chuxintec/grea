Shader "Monkey/SpineSourceGraphicProfile/Colored"
{
    Properties
    {
        [PerRendererData] _MainTex ("Spine Atlas", 2D) = "white" {}
        [Enum(UnityEngine.Rendering.BlendMode)] _SrcBlend ("Source Blend", Float) = 5
        [Enum(UnityEngine.Rendering.BlendMode)] _DstBlend ("Destination Blend", Float) = 10
        [Toggle(_STRAIGHT_ALPHA_INPUT)] _StraightAlphaInput ("Straight Alpha Texture", Int) = 0
        [Toggle(_CANVAS_GROUP_COMPATIBLE)] _CanvasGroupCompatible ("CanvasGroup Compatible", Int) = 1
        [Toggle(_PREMULTIPLIED_ALPHA)] _PremultipliedAlpha ("Premultiplied Alpha Profile", Int) = 1
        _Color ("Tint", Color) = (1,1,1,1)

        [HideInInspector][Enum(UnityEngine.Rendering.CompareFunction)] _StencilComp ("Stencil Comparison", Float) = 8
        [HideInInspector] _Stencil ("Stencil ID", Float) = 0
        [HideInInspector][Enum(UnityEngine.Rendering.StencilOp)] _StencilOp ("Stencil Operation", Float) = 0
        [HideInInspector] _StencilWriteMask ("Stencil Write Mask", Float) = 255
        [HideInInspector] _StencilReadMask ("Stencil Read Mask", Float) = 255
        [HideInInspector] _ColorMask ("Color Mask", Float) = 15
        [Toggle(UNITY_UI_ALPHACLIP)] _UseUIAlphaClip ("Use Alpha Clip", Float) = 0
    }

    SubShader
    {
        Tags
        {
            "Queue"="Transparent"
            "IgnoreProjector"="True"
            "RenderType"="Transparent"
            "PreviewType"="Plane"
            "CanUseSpriteAtlas"="True"
        }

        Stencil
        {
            Ref [_Stencil]
            Comp [_StencilComp]
            Pass [_StencilOp]
            ReadMask [_StencilReadMask]
            WriteMask [_StencilWriteMask]
        }

        Cull Off
        Lighting Off
        ZWrite Off
        ZTest [unity_GUIZTestMode]
        Fog { Mode Off }
        Blend [_SrcBlend] [_DstBlend]
        ColorMask [_ColorMask]

        Pass
        {
            Name "Normal"
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 2.0
            #pragma shader_feature _ _STRAIGHT_ALPHA_INPUT
            #pragma shader_feature _ _CANVAS_GROUP_COMPATIBLE
            #pragma shader_feature _ _PREMULTIPLIED_ALPHA
            #pragma multi_compile __ UNITY_UI_ALPHACLIP
            #include "UnityCG.cginc"
            #include "UnityUI.cginc"

            struct VertexInput
            {
                float4 vertex : POSITION;
                float4 color : COLOR;
                float2 texcoord : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct VertexOutput
            {
                float4 vertex : SV_POSITION;
                fixed4 color : COLOR;
                half2 texcoord : TEXCOORD0;
                float4 worldPosition : TEXCOORD1;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            sampler2D _MainTex;
            fixed4 _Color;
            fixed4 _TextureSampleAdd;
            float4 _ClipRect;

            VertexOutput vert (VertexInput input)
            {
                VertexOutput output;
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);
                output.worldPosition = input.vertex;
                output.vertex = UnityObjectToClipPos(output.worldPosition);
                #ifdef UNITY_HALF_TEXEL_OFFSET
                output.vertex.xy += (_ScreenParams.zw - 1.0) * float2(-1, 1);
                #endif
                output.texcoord = input.texcoord;
                #if defined(_PREMULTIPLIED_ALPHA)
                output.color = input.color * float4(_Color.rgb * _Color.a, _Color.a);
                #else
                output.color = input.color * _Color;
                #endif
                return output;
            }

            fixed4 frag (VertexOutput input) : SV_Target
            {
                half4 textureColor = tex2D(_MainTex, input.texcoord);
                #if defined(_STRAIGHT_ALPHA_INPUT)
                textureColor.rgb *= textureColor.a;
                #endif
                half4 color = (textureColor + _TextureSampleAdd) * input.color;
                #if defined(_CANVAS_GROUP_COMPATIBLE)
                color.rgb *= input.color.a;
                #endif
                color *= UnityGet2DClipping(input.worldPosition.xy, _ClipRect);
                #ifdef UNITY_UI_ALPHACLIP
                clip(color.a - 0.001);
                #endif
                return color;
            }
            ENDCG
        }
    }
}
