using UnityEngine;
using UnityEngine.EventSystems;
namespace Grea.LifecycleSample {
 public sealed class PointerEvidence:MonoBehaviour,IPointerClickHandler {
  public CounterController controller;
  public void OnPointerClick(PointerEventData data){controller.Trace("pointer:"+name+":"+data.button+":"+data.position.x+","+data.position.y);}
 }
}
