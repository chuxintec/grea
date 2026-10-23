using UnityEngine;
namespace Grea.LifecycleSample {
 public sealed class InputEvidence:MonoBehaviour {
  public CounterController controller;
  void Update(){if(Input.GetMouseButtonDown(0))controller.Trace("raw-down:"+Input.mousePosition+":focus="+Application.isFocused);if(Input.GetMouseButtonUp(0))controller.Trace("raw-up:"+Input.mousePosition+":focus="+Application.isFocused);if(Input.GetKeyDown(KeyCode.Return))controller.Trace("raw-return:focus="+Application.isFocused);}
  void OnApplicationFocus(bool focused){if(controller!=null)controller.Trace("focus:"+focused);}
 }
}
