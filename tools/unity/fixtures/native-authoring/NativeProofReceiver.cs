using UnityEngine;
using Own.Configuration;
using System.Collections;
using System.Linq;
namespace Own.Proof
{
    public sealed class NativeProofReceiver : MonoBehaviour
    {
        public EnemyTable enemies;
        public HintTable hints;
        public int pulses;
        public void Pulse() { pulses++; }
        public bool ConfigurationValid() => enemies && enemies.rows.Length==2 && enemies.rows[0].Health==25 &&
            hints && hints.rows.Length==2 && !hints.rows[0].Enabled && hints.rows[0].Text==null && hints.rows[1].Text=="";
        IEnumerator Start()
        {
            if(!ConfigurationValid()) throw new System.InvalidOperationException("Typed SO Player readback mismatch");
            Debug.Log("GREA_NATIVE_PROOF_PLAYER_CONFIG_OK");
            if(!System.Environment.GetCommandLineArgs().Contains("-grea-native-proof"))yield break;
            yield return null;
            var animator=GetComponent<Animator>();animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;
            animator.Play("Move",0,0);animator.Update(0);animator.Update(0.5f);
            if(Mathf.Abs(transform.Find("Widget").localPosition.x-4)>0.05f || pulses<1 || transform.Find("Widget").localScale!=new Vector3(2,3,1))throw new System.InvalidOperationException("Native Player animation/manual edit/event mismatch");
            animator.Play("Return",0,0.5f);animator.Update(0);
            if(Mathf.Abs(transform.Find("Widget").localPosition.x-2)>0.05f)throw new System.InvalidOperationException("Native Player interruption mismatch");
            animator.Play("Move",0,0.99f);animator.Update(0);animator.Update(0.03f);
            if(transform.Find("Widget").localPosition.x>0.3f)throw new System.InvalidOperationException("Native Player loop seam mismatch");
            Debug.Log("GREA_NATIVE_PROOF_PLAYER_ANIMATION_OK");Application.Quit(0);
        }
    }
}
