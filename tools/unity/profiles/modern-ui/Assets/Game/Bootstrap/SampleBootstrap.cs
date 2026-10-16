using System;
using System.IO;
using Grea.Foundation.Runtime;
using ModernSample.Gameplay;
using ModernSample.Services;
using ModernSample.Presentation;
using UnityEngine;
namespace ModernSample.Bootstrap
{
    public sealed class SampleBootstrap : MonoBehaviour
    {
        public SampleConfig config;
        public SampleView view;
        void Start()
        {
            if(!config || !view || config.enemyHealth<1 || config.damage<1)throw new InvalidOperationException("Valid authored config and view required");
            var args=Environment.GetCommandLineArgs();int flag=Array.IndexOf(args,"--grea-qa-root");
            bool qa=Array.IndexOf(args,"--grea-qa")>=0;
            if(qa!=(flag>=0) || qa && (flag+1>=args.Length || !Path.IsPathRooted(args[flag+1])))throw new InvalidOperationException("Explicit QA root required");
            var save=new FileSaveStore(qa?args[flag+1]:Application.persistentDataPath,"modern-"+config.kind.ToString().ToLowerInvariant(),"modern-qa-"+config.kind.ToString().ToLowerInvariant(),qa);
            // Recovery is explicit in the sample composition and logged, never hidden in Read.
            Debug.Log("MODERN_RECOVERY "+save.Recover());
            var session=new Session(new ProgressStore(save),config.kind,config.enemyHealth,config.damage);
            view.Initialize(session);Debug.Log("MODERN_READY "+config.kind+" actions="+session.Progress.Actions);
            if(qa && Array.IndexOf(args,"--grea-qa-exit-after-ready")>=0)StartCoroutine(ExitAfterReady());
        }
        System.Collections.IEnumerator ExitAfterReady()
        { yield return null; yield return null; Application.Quit(0); }
    }
}
