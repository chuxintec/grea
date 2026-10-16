// Self-owned QA only: observes native renderers/Animator; never interprets a source-engine recipe.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Rendering;

namespace Own.Proof
{
    public sealed class NativeProofVisual : MonoBehaviour
    {
        public Camera proofCamera;
        public GameObject actor;
        public SpriteRenderer shortSlice,longSlice;
        public static readonly string[] Phases={"start","manual-midpoint","near-end","loop-crossing","return-interruption"};
        public static readonly float[] Positions={0,4,7.992f,0.16f,2};
        public static readonly float[] Scales={2,3,3.998f,2.04f,2};
        void Awake(){if(proofCamera)proofCamera.aspect=1.6f;}
        [Serializable] public sealed class Frame {public string phase;public int width,height,pulses;public float expected_x,actual_x,expected_scale,actual_scale;public int pixel_assertions;public string file;}
        [Serializable] public sealed class Receipt {public int schema_version=1;public string status,build_guid,unity_version,graphics,scope="Actual Player backbuffer pixels, native renderers and Animator; no OS input claim",error;public Frame[] frames;}
        static void Require(bool value,string reason){if(!value)throw new InvalidOperationException(reason);}
        public void Pose(int phase)
        {
            var animator=actor.GetComponent<Animator>();animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;animator.speed=1;
            animator.Play("Move",0,0);animator.Update(0);
            if(phase==1)animator.Update(0.5f);
            if(phase==2){animator.Play("Move",0,0.999f);animator.Update(0);}
            if(phase==3){animator.Play("Move",0,0.99f);animator.Update(0);animator.Update(0.03f);}
            if(phase==4){animator.Update(0.5f);animator.Play("Return",0,0.5f);animator.Update(0);}
            animator.speed=0;
        }
        public Texture2D Render(int width=960,int height=600)
        {
            Require(SystemInfo.graphicsDeviceType!=GraphicsDeviceType.Null,"Real graphics device required");
            var rt=new RenderTexture(width,height,24,RenderTextureFormat.ARGB32);var target=proofCamera.targetTexture;var active=RenderTexture.active;
            var image=new Texture2D(width,height,TextureFormat.RGB24,false);
            try{proofCamera.aspect=(float)width/height;proofCamera.targetTexture=rt;proofCamera.Render();RenderTexture.active=rt;image.ReadPixels(new Rect(0,0,width,height),0,0);image.Apply();return image;}
            catch{Destroy(image);throw;}
            finally{proofCamera.targetTexture=target;RenderTexture.active=active;rt.Release();Destroy(rt);}
        }
        Color Pixel(Texture2D image,Vector3 world)
        {
            var point=proofCamera.WorldToViewportPoint(world);
            Require(point.z>0&&point.x>0&&point.x<1&&point.y>0&&point.y<1,"Probe outside camera frame: "+world);
            return image.GetPixel(Mathf.Clamp(Mathf.RoundToInt(point.x*image.width),0,image.width-1),Mathf.Clamp(Mathf.RoundToInt(point.y*image.height),0,image.height-1));
        }
        static bool Near(Color a,Color b)=>Mathf.Abs(a.r-b.r)<0.12f&&Mathf.Abs(a.g-b.g)<0.12f&&Mathf.Abs(a.b-b.b)<0.12f;
        public int Check(Texture2D image,int phase)
        {
            int checks=0;Color background=image.GetPixel(3,3);
            Action<Vector3,Color,string> color=(world,wanted,label)=>{var actual=Pixel(image,world);Require(Near(actual,wanted),Phases[phase]+" "+label+" at "+world+" expected "+wanted+" observed "+actual);checks++;};
            float x=Positions[phase],scale=Scales[phase];
            Require(Vector3.Distance(proofCamera.transform.position,new Vector3(0,0,-10))<0.001f&&proofCamera.orthographic&&proofCamera.orthographicSize==5,"Explicit camera framing");
            Require(Mathf.Abs(actor.transform.Find("Widget").localPosition.x-x)<0.01f,"Native position");
            Require(Mathf.Abs(actor.transform.Find("Other").localScale.y-scale)<0.01f,"Native scale");
            // Independent expected source pixels, bottom-left coordinates after undoing CW rotation.
            Color[,] pattern={{Color.red,Color.blue,Color.magenta},{Color.green,Color.yellow,Color.cyan}};
            Func<int,int,Vector3> trim=(px,py)=>new Vector3(-4+x+(px+0.5f-1.25f)*0.4f,2.2f+(py+0.5f-3)*0.6f,0);
            for(int row=0;row<2;row++)for(int col=0;col<3;col++)color(trim(col+1,row+1),pattern[row,col],"unrotated trimmed texel");
            color(trim(0,2),background,"left transparent restoration");color(trim(4,2),background,"right transparent restoration");color(trim(2,3),background,"top transparent restoration");
            color(new Vector3(-4+x,2.2f,0),Color.black,"visible pivot anchor");
            color(new Vector3(-0.35f,-1.6f+0.35f*scale,0),Color.red,"visible animated scale upper-left");
            color(new Vector3(0.35f,-1.6f-0.35f*scale,0),Color.yellow,"visible animated scale lower-right");
            color(new Vector3(0,-1.6f+0.50f*scale,0),background,"outside scaled target");
            foreach(var slice in new[]{shortSlice,longSlice})
            {
                Vector3 c=slice.transform.position;float halfX=slice.size.x/2,halfY=slice.size.y/2;
                color(c+new Vector3(-halfX+0.1f,halfY-0.1f,0),Color.red,"sliced top-left corner");
                color(c+new Vector3(halfX-0.1f,halfY-0.1f,0),Color.green,"sliced top-right corner");
                color(c+new Vector3(-halfX+0.1f,-halfY+0.1f,0),Color.blue,"sliced bottom-left corner");
                color(c+new Vector3(halfX-0.1f,-halfY+0.1f,0),Color.yellow,"sliced bottom-right corner");
                color(c,Color.white,"sliced center");
                var edge=Pixel(image,c+new Vector3(-halfX+0.3f,halfY-0.1f,0));
                Require(Mathf.Abs(edge.r-edge.g)<0.03f&&Mathf.Abs(edge.g-edge.b)<0.03f&&edge.r>0.2f&&edge.r<0.8f,"Nine-slice corner width must stay 0.2 world units at two sizes");checks++;
            }
            return checks;
        }
        IEnumerator Start()
        {
            var args=Environment.GetCommandLineArgs();int at=Array.IndexOf(args,"-grea-visual-proof");if(at<0)yield break;
            string output=null;var rows=new List<Frame>();var receipt=new Receipt {status="started",build_guid=Application.buildGUID,unity_version=Application.unityVersion,graphics=SystemInfo.graphicsDeviceType.ToString()};
            try
            {
                if(at+1>=args.Length||!Path.IsPathRooted(args[at+1])||Directory.Exists(args[at+1])||File.Exists(args[at+1]))throw new IOException("New explicit capture directory required");
                output=args[at+1];Directory.CreateDirectory(output);Application.runInBackground=true;Pose(0);Screen.SetResolution(960,600,FullScreenMode.Windowed);
            }
            catch(Exception e){Debug.LogException(e);Application.Quit(1);yield break;}
            yield return null;
            // Player startup can still composite the native splash fade over otherwise-correct pixels.
            float deadline=Time.realtimeSinceStartup+15;
            while(!SplashScreen.isFinished)
            {
                if(Time.realtimeSinceStartup>deadline)
                {
                    receipt.status="failed";receipt.error="Native splash did not finish within 15 seconds";receipt.frames=rows.ToArray();File.WriteAllText(Path.Combine(output,"receipt.json"),JsonUtility.ToJson(receipt,true));Application.Quit(1);yield break;
                }
                yield return null;
            }
            yield return new WaitForEndOfFrame();yield return null;
            Debug.Log("NATIVE_VISUAL_SPLASH_READY isFinished="+SplashScreen.isFinished);
            for(int phase=0;phase<Phases.Length;phase++)
            {
                Pose(phase);yield return null;yield return new WaitForEndOfFrame();
                Texture2D image=null;bool failed=false;
                try
                {
                    image=ScreenCapture.CaptureScreenshotAsTexture();
                    string name=phase+"-"+Phases[phase]+".png";File.WriteAllBytes(Path.Combine(output,name),image.EncodeToPNG());
                    if(phase==0)
                    {
                        var source=actor.transform.Find("Widget/Graphic").GetComponent<SpriteRenderer>();var texture=source.sprite.texture;
                        Debug.Log("NATIVE_VISUAL_PLAYER_SOURCE format="+texture.format+" size="+texture.width+"x"+texture.height+" filter="+texture.filterMode+" texel="+texture.GetPixel(1,1)+" renderer="+source.color+" shader="+source.sharedMaterial.shader.name+" screen="+Screen.width+"x"+Screen.height+" image="+image.width+"x"+image.height+" aspect="+proofCamera.aspect);
                        var reference=Render();try{File.WriteAllBytes(Path.Combine(output,"offscreen-reference.png"),reference.EncodeToPNG());Debug.Log("NATIVE_VISUAL_PLAYER_REFERENCE red="+Pixel(reference,new Vector3(-3.9f,1.3f,0)));}finally{Destroy(reference);}
                    }
                    int count=Check(image,phase);
                    rows.Add(new Frame {phase=Phases[phase],file=name,width=image.width,height=image.height,expected_x=Positions[phase],actual_x=actor.transform.Find("Widget").localPosition.x,expected_scale=Scales[phase],actual_scale=actor.transform.Find("Other").localScale.y,pulses=actor.GetComponent<NativeProofReceiver>().pulses,pixel_assertions=count});
                }
                catch(Exception e){receipt.status="failed";receipt.error=e.ToString();Debug.LogException(e);failed=true;}
                finally{if(image)Destroy(image);}
                if(failed){receipt.frames=rows.ToArray();File.WriteAllText(Path.Combine(output,"receipt.json"),JsonUtility.ToJson(receipt,true));Application.Quit(1);yield break;}
            }
            receipt.status="rendered_checks_passed";receipt.frames=rows.ToArray();File.WriteAllText(Path.Combine(output,"receipt.json"),JsonUtility.ToJson(receipt,true));
            Debug.Log("GREA_NATIVE_VISUAL_PLAYER_OK "+rows.Count+" actual backbuffer frames");Application.Quit(0);
        }
    }
}
