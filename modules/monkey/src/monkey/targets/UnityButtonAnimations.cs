// Editor-only native button animation assets. Identity paths come from the frozen plan.
using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEditor.Animations;

public static partial class MonkeyImporter
{
    internal static AnimatorController CreateScaleButtonController(string controllerPath,string normalPath,string pressedPath,Vector3 scale,float zoom,float duration)
    {
        foreach(var path in new[]{controllerPath,normalPath,pressedPath}) {
            if(!path.StartsWith("Assets/",StringComparison.Ordinal)||path.Contains("..")||path.Contains("\\")||System.Text.Encoding.UTF8.GetByteCount(Path.GetFileName(path))>64)
                throw new InvalidOperationException("Unsafe or oversized button animation path");
        }
        var controller=AnimatorController.CreateAnimatorControllerAtPath(controllerPath);
        var normal=new AnimationClip {name="Normal"};var pressed=new AnimationClip {name="Pressed"};
        foreach(var axis in new[]{"x","y","z"}) {
            var value=axis=="x"?scale.x:axis=="y"?scale.y:scale.z;
            normal.SetCurve("",typeof(Transform),"m_LocalScale."+axis,AnimationCurve.Constant(0,Mathf.Max(duration,.001f),value));
            pressed.SetCurve("",typeof(Transform),"m_LocalScale."+axis,AnimationCurve.Constant(0,Mathf.Max(duration,.001f),value*zoom));
        }
        AssetDatabase.CreateAsset(normal,normalPath);AssetDatabase.CreateAsset(pressed,pressedPath);
        var machine=controller.layers[0].stateMachine;
        foreach(var trigger in new[]{"Normal","Highlighted","Pressed","Selected","Disabled"}) {
            controller.AddParameter(trigger,AnimatorControllerParameterType.Trigger);
            var state=machine.AddState(trigger);state.motion=trigger=="Pressed"?pressed:normal;
            var transition=machine.AddAnyStateTransition(state);transition.AddCondition(AnimatorConditionMode.If,0,trigger);
            transition.hasExitTime=false;transition.hasFixedDuration=true;transition.duration=duration;transition.canTransitionToSelf=false;
            if(trigger=="Normal")machine.defaultState=state;
        }
        EditorUtility.SetDirty(controller);AssetDatabase.SaveAssetIfDirty(controller);
        return controller;
    }
}
