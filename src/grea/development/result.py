"""Construct development receipts for both CLI adapters and structured actions."""
import uuid
from pathlib import Path

from . import __version__
from .errors import BeaverError
from .implementation import identity
from .io import sha


def development_result(arguments, *, operation, parse=None):
    run_id = uuid.uuid4().hex
    base = dict(schemaVersion=1, contract="grea-development-result/1", operationId=run_id,
                producer=dict(name="grea", version=__version__, implementationSha256=identity()),
                actualChanges=[], artifacts=[], diagnostics=[], limitations=[],
                verification=dict(native="not_run", player="not_run", visual="not_run", business="not_run"))
    a = arguments
    try:
        if a is None:
            a = parse()
        data = operation(a)
        status = data.get("status") if data.get("status") in ("blocked","partial","failed","not_run") else "ok"
        if a.command=='ui' and data.get('status')=='issues':status='partial'
        if data.get('status') in ('identity_unknown','starting','stopping','not_available'):status='partial'
        if data.get('status')=='needs_action':status='blocked'
        if data.get('status') in ('stale_plan','migration_order_blocked','blocked_existing_output','partial_or_untracked_database'):status='blocked'
        if data.get('status')=='failed_or_needs_action':status='failed'
        if data.get('status') in ('execution_unknown_or_failed','execution_unknown_or_partial'):status='partial'
        if a.command=='qa' and data.get('status') in ('recovery_required','observed_running','stopped_by_budget','interrupted'):status='partial'
        if a.command=='qa' and a.action.startswith('virtual-'):
            if data.get('status')=='unknown':status='partial'
            if data.get('status')=='not_supported':status='blocked'
            data.update(inputMode='virtual-pointer',backend='unity-inputsystem-virtual-pointer/1')
        if a.command=='build-filter' and a.action=='plan' and data.get('execution',{}).get('status')=='blocked':status='blocked'
        base.update(status=status, data=data)
        result_path = data.get("report")
        if a.command=='qa' and a.action.startswith('virtual-') and not result_path:
            result_path=next((data[k] for k in ('receipt','session','channel') if isinstance(data.get(k),str)),None)
        if result_path and Path(result_path).is_file():
            base["artifacts"].append(dict(path=result_path, sha256=sha(Path(result_path).read_bytes())))
        if data.get("nativeReadback"):
            base["verification"]["native"] = data["nativeReadback"]
        if a.command == "adopt" and a.action == "apply":
            base["actualChanges"] = [dict(operation='adoption.apply',transaction=data['transaction'],counts=data.get('counts',{}))]
        if a.command=='intake' and a.action in ('apply','rollback'):
            base['actualChanges']=[dict(operation='intake.'+a.action,transaction=data.get('transaction',a.transaction if a.action=='rollback' else a.out),additions=data.get('additions'),restored=data.get('restored'))]
            base['verification']['native']=data.get('native','rolled_back' if a.action=='rollback' else 'verified-declared-intake-subset')
        if a.command=='intake' and a.action=='prepare-bindings':
            base['actualChanges']=[dict(operation='intake.prepare-bindings',preparationDirectory=a.out,targetProjectWrites=False)]
            base['verification']['native']=data.get('native','not_run')
        if a.command=='intake' and a.action=='export-bindings':
            base['actualChanges']=[dict(operation='intake.export-bindings',exportDirectory=a.out,targetProjectWrites=False,originalPreparationWrites=False)]
            base['verification']['native']=data.get('native','not_run')
        if a.command == "unity" and a.action == "apply":
            base["actualChanges"] = data.get("changes", [])
        if a.command=='unity' and a.action=='recover':
            base['actualChanges']=[dict(operation=data.get('operation','assets.retire.recover'),transaction=data['transaction'],restoredFiles=data.get('restoredFiles'),deletedPaths=data.get('deletedPaths'),deletedFolders=data.get('deletedFolders',[]))]
        if a.command=='unity' and a.action=='recover-font-source':
            base['actualChanges']=[dict(operation='build.font-source.recover',report=data.get('report'),restoredFiles=len(data.get('restored',[])))]
        if a.command in ('batch','production') and a.action in ('apply','recover'):
            base['actualChanges']=data.get('changes',[dict(operation=a.command+'.recover',restored=data.get('restored'))])
        if a.command=='workspace' and a.action=='apply':
            base['actualChanges']=[dict(operation='workspace.binding',path=data['profile'],sha256=data['profileSha256'])]
        if a.command=='server' and a.action=='migration-apply' and data.get('execution')!='not_run':
            base['actualChanges']=[dict(operation='server.migration',projectName=a.project_name,owner=a.owner,database=data.get('database'),status=data.get('status'),stateBeforeSha256=data.get('stateBeforeSha256'),stateAfterSha256=data.get('stateAfterSha256'))]
        if a.command=='server':
            output_path=data.get('composePath') or (a.out if a.action=='migration-plan' else None)
            if output_path and Path(output_path).is_file():base['artifacts'].append(dict(path=str(Path(output_path).resolve()),sha256=sha(Path(output_path).read_bytes())))
        if a.command=='adopt' and a.action=='finalize':
            base['actualChanges']=[dict(operation='adoption.finalize',transaction=a.transaction,report=data.get('report'))]
        if a.command=='adopt' and a.action=='rollback':
            base['verification']['native']='rolled_back'
            base['actualChanges']=[dict(operation='adoption.rollback',restored=data.get('restored'),report=data.get('report'))]
        if a.command=='player':
            base['verification']['player']='launched_and_exited' if not data.get('stoppedByBudget') else 'launched_and_stopped_by_budget'
        if a.command=='qa':
            if a.action.startswith('virtual-'):
                base['verification']['virtualInput']=('application-device-consumed' if data.get('status') in ('verified','consumed') else 'not_verified') if a.action=='virtual-input' else ('device-cleanup-receipt' if a.action=='virtual-stop' else 'not_dispatched')
                base['actualChanges']=[dict(operation='qa.'+a.action,inputMode='virtual-pointer',backend=data['backend'],receipt=data.get('receipt'),status=data.get('status'))]
            elif a.action=='prepare':
                base['actualChanges']=[dict(operation='qa.prepare',project=data.get('projectId'),build=data.get('buildId'),profile=data.get('profileId'),receipt=data.get('receipt'))]
            elif a.action=='launch':
                base['actualChanges']=[dict(operation='qa.launch',runId=data.get('runId'),pid=data.get('pid'),processRecord=data.get('processRecord'))]
                base['verification']['player']=data.get('status','unknown')
                if data.get('stoppedByBudget'):base['status']='partial';status='partial'
            elif a.action=='bind':
                base['verification']['native']='attach-only-window-bound' if data.get('status')=='bound' else 'not_bound'
            elif a.action=='input':
                native_input=data.get('native',{})
                if native_input.get('eventsPosted',0) or native_input.get('axActionsAttempted',0) or native_input.get('cursorSync',{}).get('attempted'):
                    effect=dict(operation='qa.input',pid=data.get('pid'),windowId=data.get('windowId'),eventsPosted=native_input.get('eventsPosted',0),axActionsAttempted=native_input.get('axActionsAttempted',0),axActionsPerformed=native_input.get('axActionsPerformed',0))
                    if 'cursorSync' in native_input:effect['cursorSync']=native_input['cursorSync']
                    if 'cursorSyncHistory' in native_input:effect['cursorSyncHistory']=native_input['cursorSyncHistory']
                    base['actualChanges']=[effect]
                base['verification']['native']=data.get('native',{}).get('inputDelivery','window-only-observation')
        if a.command=='payload' and a.action=='apply':
            base['actualChanges']=[dict(operation='payload.materialize',targetRoot=data['targetRoot'],files=data['files'],overrides=len(data['overrides']))]
        if getattr(a,'summary',False):
            from .reporting import _p0_summary
            base['data']=_p0_summary(data)
            if isinstance(base['verification']['native'],dict):
                native=base['verification']['native']
                base['verification']['native']={k:native[k] for k in ('status','operation','mode','planSha256','sourceSha256') if k in native}
                base['verification']['native']['detailReport']=result_path
            if a.command=='unity' and a.action in ('apply','recover'):
                base['actualChanges']=[dict(operation='unity.'+a.action,transaction=data.get('transaction'),changeRecords=len(data.get('changes',[])),restoredFiles=data.get('restoredFiles'),detailReport=result_path)]
        return base, {'blocked':3,'partial':1,'failed':2,'not_run':3}.get(status,0)
    except (BeaverError, OSError, ValueError, TypeError, KeyError, ImportError, OverflowError) as error:
        blocked=isinstance(error,BeaverError) and error.status=='blocked'
        base.update(status="blocked" if blocked else "failed",
                    diagnostics=[error.as_dict() if isinstance(error, BeaverError) else dict(code="IO_OR_INPUT", location="input", message=str(error))])
        if getattr(a,'command',None)=='qa':
            from .qa_runtime import failure_receipt
            qa_receipt=failure_receipt(error)
            if qa_receipt:
                base['actualChanges']=[dict(status='inspect_qa_runtime_receipt',report=qa_receipt,reason='Runtime operations can fail after controlled Data or owned-process effects; inspect the recorded transaction')]
        if getattr(a,'command',None)=='unity' and a.action=='recover-font-source' and Path(a.out,'recovery-result.json').is_file():
            base['actualChanges']=[dict(status='inspect_recovery_receipt',report=str(Path(a.out,'recovery-result.json')),reason='Recovery can fail after partial writes; inspect the separate receipt')]
        if isinstance(error,BeaverError):
            if getattr(a,'command',None)=='intake' and a.action=='export-bindings' and Path(a.out).is_dir():
                base['actualChanges']=[dict(status='inspect_export_directory',exportDirectory=a.out,targetProjectWrites=False,originalPreparationWrites=False,reason='New export may be incomplete; no Editor was invoked by this continuation')]
            if getattr(a,'command',None)=='intake' and a.action=='prepare-bindings' and Path(a.out).is_dir():
                base['actualChanges']=[dict(status='inspect_isolated_preparation_copy',preparationDirectory=a.out,targetProjectWrites=False,reason='Native preparation may have failed after isolated writes; preserve evidence; output is not adoptable')]
                from .intake_bindings import failed_native_attempts
                try:
                    attempts=failed_native_attempts(a.out)
                    if attempts:
                        base['verification']['native']='failed' if all(p['exited'] for p in attempts) else 'attempted_exit_pending'
                        base['actualChanges'][0]['nativeProcesses']=attempts
                except (BeaverError,OSError,ValueError):
                    base['verification']['native']='unknown_process_receipt'
            if getattr(a,'command',None)=='intake' and a.action in ('apply','rollback'):
                stage=Path(a.out if a.action=='apply' else a.transaction)
                if (stage/'journal.json').is_file():
                    base['actualChanges']=[dict(status='inspect_intake_transaction',transaction=str(stage),reason='Failure may follow temporary helper or native writes; inspect the owned journal, never automatically replay')]
                    base['artifacts'].append(dict(path=str(stage/'journal.json'),sha256=sha((stage/'journal.json').read_bytes())))
                    if error.code=='INTAKE_NATIVE_FAILED':
                        base['verification']['native']='failed; inspect partial transaction'
                    elif any(stage.glob('native-*.json')) and error.code not in ('INTAKE_ROLLBACK_CONFLICT','INTAKE_RECOVERY_STATE','INTAKE_IMPLEMENTATION','INTAKE_PLAN_CHANGED'):
                        base['verification']['native']='unknown for this call; inspect recorded transaction'
            if error.code=='READBACK_PROJECT_MODIFIED':
                base['actualChanges']=[dict(status='inspect_source_guard',guard=error.location,reason='Read-only guard failed; inspect witnessed paths and helper before retry')]
            location=Path(error.location)
            if location.is_dir() and (location/'journal.json').is_file():
                base['artifacts'].append(dict(path=str(location/'journal.json'),sha256=sha((location/'journal.json').read_bytes())))
                base['actualChanges']=[dict(status='inspect_transaction',transaction=str(location),reason='Failure can follow partial native writes; no zero-write claim')]
                if '_NATIVE_FAILED' in error.code:
                    base['verification']['native']='failed'
        return base, 3 if blocked else 2
