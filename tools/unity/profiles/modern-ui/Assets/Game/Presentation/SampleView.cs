using System.Threading.Tasks;
using Grea.Foundation.Contracts;
using Grea.UI.Modern;
using Grea.UI.UGUI;
using ModernSample.Domain;
using ModernSample.Gameplay;
using TMPro;
using UnityEngine;
using UnityEngine.UI;
namespace ModernSample.Presentation
{
    public sealed class SampleView : MonoBehaviour
    {
        public ModernUIRoot root;
        public TMP_Text status;
        public Button action, menu;
        readonly LifetimeScope scope=new LifetimeScope();
        Session session;
        public void Initialize(Session session)
        {
            this.session=session;
            action.GetComponent<CommandButton>().Bind(scope, stamp=>{stamp.ThrowIfStale();session.Act();Render();return Task.CompletedTask;});
            menu.GetComponent<CommandButton>().Bind(scope, stamp=>{stamp.ThrowIfStale();root.dialog.Open(scope,"暂停 / Pause");return Task.CompletedTask;});
            Render();
        }
        public void Render()
        {
            status.text=session.Kind==GameKind.Combat ? "数值战斗 / Combat\n敌人生命："+session.EnemyHealth+"\n已保存行动："+session.Progress.Actions :
                "益智 / Puzzle\n"+(session.TileAtLeft?"[ 1 ][   ]":"[   ][ 1 ]")+"\n已保存步数："+session.Progress.Actions;
        }
        void OnDestroy()=>scope.Dispose();
    }
}
