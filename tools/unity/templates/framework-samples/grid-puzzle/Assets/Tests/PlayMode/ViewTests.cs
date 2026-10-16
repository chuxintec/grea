using System.Collections;
using Grea.Foundation.Contracts;
using Grea.UI.UGUI;
using Puzzle.Domain;
using Puzzle.Gameplay;
using Puzzle.Services;
using Puzzle.Presentation;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
#if UNITY_EDITOR
using UnityEditor;
#endif
namespace Puzzle.PlayTests
{
    public sealed class ViewTests
    {
        sealed class Memory : ISaveStore { string raw; public string Read()=>raw; public void Write(string value){raw=value;} }
        // RenderTexture cameras exercise the actual CanvasScaler and RectTransforms at different viewports.
        [UnityTest] public IEnumerator ViewportChangesKeepEveryPageButtonVisibleAndSeparated()
        {
#if UNITY_EDITOR
            var go=Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>("Assets/SampleView.prefab"));
            var cameraObject=new GameObject("ViewportTestCamera",typeof(Camera));
            var camera=cameraObject.GetComponent<Camera>(); RenderTexture target=null;
            try
            {
                var host=go.GetComponent<UIHost>(); host.enabled=false;
                host.canvas.renderMode=RenderMode.ScreenSpaceCamera; host.canvas.worldCamera=camera;
                camera.transform.position=new Vector3(0,0,-10); camera.orthographic=true;
                camera.clearFlags=CameraClearFlags.SolidColor; camera.enabled=false;
                foreach(var size in new[]{new Vector2Int(540,900),new Vector2Int(3024,1834),new Vector2Int(900,540)})
                {
                    if(target) { camera.targetTexture=null; Object.Destroy(target); }
                    target=new RenderTexture(size.x,size.y,0); target.Create(); camera.targetTexture=target;
                    host.ApplySafeArea(new Rect(0,0,size.x,size.y),new Vector2(size.x,size.y));
                    yield return null; yield return null; Canvas.ForceUpdateCanvases();
                    Assert.Less(Vector2.Distance((Vector2)size,host.canvas.renderingDisplaySize),.1f,"Use the requested viewport, not the Editor window");
                    var canvasRect=(RectTransform)host.canvas.transform;
                    var buttons=host.pageLayer.GetComponentsInChildren<UnityEngine.UI.Button>(true);
                    var bounds=new Rect[buttons.Length]; var corners=new Vector3[4];
                    for(int i=0;i<buttons.Length;i++)
                    {
                        ((RectTransform)buttons[i].transform).GetWorldCorners(corners);
                        Vector2 low=canvasRect.InverseTransformPoint(corners[0]), high=canvasRect.InverseTransformPoint(corners[2]);
                        bounds[i]=Rect.MinMaxRect(low.x,low.y,high.x,high.y);
                        Assert.Greater(bounds[i].width,0); Assert.Greater(bounds[i].height,0);
                        Assert.That(low.x,Is.GreaterThanOrEqualTo(canvasRect.rect.xMin-.1f));
                        Assert.That(low.y,Is.GreaterThanOrEqualTo(canvasRect.rect.yMin-.1f));
                        Assert.That(high.x,Is.LessThanOrEqualTo(canvasRect.rect.xMax+.1f));
                        Assert.That(high.y,Is.LessThanOrEqualTo(canvasRect.rect.yMax+.1f));
                        for(int j=0;j<i;j++) Assert.IsFalse(bounds[i].Overlaps(bounds[j]),
                            size+": "+buttons[i].name+" overlaps "+buttons[j].name);
                    }
                }
            }
            finally { camera.targetTexture=null; if(target) Object.Destroy(target); Object.Destroy(cameraObject); Object.Destroy(go); }
            yield return null;
#else
            Assert.Ignore("Editor prefab viewport integration; native window resize is separate"); yield break;
#endif
        }
        [UnityTest] public IEnumerator SharedPrefabsDispatchOnceAndSurviveCancellationFailureAndReentry()
        {
#if UNITY_EDITOR
            var prefab=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/SampleView.prefab"); Assert.IsNotNull(prefab);
            var go=Object.Instantiate(prefab);
            try
            {
                var host=go.GetComponent<UIHost>(); var view=go.GetComponent<PuzzleView>();
                var persistence=new Persistence(new Memory()); var session=new PuzzleSession(persistence);
                view.Initialize(session,true,()=>persistence.FailNextWrite=true); yield return null;
                Assert.AreEqual(view.tiles[0].gameObject,host.events.currentSelectedGameObject);

                view.tiles[0].onClick.Invoke(); view.move.onClick.Invoke(); Assert.AreEqual(0,session.Board.Moves);
                view.tiles[5].onClick.Invoke(); view.cancel.onClick.Invoke(); Assert.AreEqual(0,session.Selected);
                view.tiles[5].onClick.Invoke(); view.move.onClick.Invoke(); Assert.AreEqual(1,session.Board.Moves);
                view.reset.onClick.Invoke(); Assert.IsTrue(host.modal.IsOpen); host.modal.CloseButton.onClick.Invoke();
                Assert.AreEqual(1,session.Board.Moves);
                persistence.FailNextWrite=true; view.tiles[8].onClick.Invoke(); view.move.onClick.Invoke();
                StringAssert.Contains("SAVE ERROR",view.status.text); Assert.AreEqual(1,session.Board.Moves);
                host.modal.Close(); view.move.onClick.Invoke(); Assert.IsTrue(session.Board.Solved); Assert.AreEqual(1,session.Board.Wins);
                host.gameObject.SetActive(false); host.gameObject.SetActive(true); yield return null;
                view.reset.onClick.Invoke(); view.modalAction.onClick.Invoke(); Assert.AreEqual(0,session.Board.Moves);

                using (var navigationScope=new LifetimeScope())
                {
                    host.modal.Close(); view.modalAction.gameObject.SetActive(true); host.modal.Open(navigationScope);
                    Assert.AreSame(view.modalAction,host.modal.CloseButton.FindSelectableOnUp(),"Modal navigation must not escape to background controls");
                    Assert.AreSame(host.modal.CloseButton,view.modalAction.FindSelectableOnDown());
                    host.modal.Close();
                }
                Assert.AreEqual(1,go.GetComponentsInChildren<UnityEngine.EventSystems.EventSystem>(true).Length);
                host.modal.Close(); Assert.IsFalse(host.modal.IsOpen);
            }
            finally { Object.Destroy(go); }
            yield return null;
#else
            Assert.Ignore("Editor native prefab integration; physical Player input is separate"); yield break;
#endif
        }
    }
}
