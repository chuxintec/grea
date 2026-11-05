"""Admission of saved Unity observations, separate from source acceptance."""
import re
from pathlib import PurePosixPath

from .unity_verification_contract import NATIVE_IMPORT_STATUSES, SAVED_SOURCE_SCOPES

_UNSET=object()


def saved_readback_admission(readback, *, gallery=False, expected_plan_sha256=_UNSET, expected_source_manifest_sha256=_UNSET):
    """Check the producer state and inventory used by every public consumer.

    This validates the observation envelope, not component identity, presentation
    or gameplay. Callers still verify owned bytes and their own evidence scope.
    """
    issues=[]
    def issue(code, field, message):
        issues.append(dict(code=code,field=field,message=message))
    if not isinstance(readback,dict):
        issue('NATIVE_READBACK_INVALID','$','Expected a saved readback object')
        return dict(valid=False,issues=issues,nativeFiles={})
    if readback.get('status') not in NATIVE_IMPORT_STATUSES:
        issue('NATIVE_READBACK_STATUS_INVALID','status','Unsupported native import status')
    if (readback.get('unityVersion')!='6000.6.2f1' or
            type(readback.get('missingScripts'))is not int or readback['missingScripts']!=0):
        issue('EDITOR_READBACK_FAILED','unityVersion/missingScripts','Exact Editor version and integer zero missing scripts required')
    valid_scope=(readback.get('nativeScope')=='resources-and-gallery-only' and readback.get('sourceGraphVerification')=='not_run')if gallery else (
        readback.get('nativeScope')in SAVED_SOURCE_SCOPES and readback.get('sourceGraphVerification')=='saved-source-node-subset')
    if not valid_scope:
        issue('NATIVE_SOURCE_GRAPH_SCOPE_INVALID','nativeScope/sourceGraphVerification','Saved scope must match the producer plan, including explicit resource-only galleries')
    if readback.get('editableRoundtrip')is not True:
        issue('EDITABLE_ROUNDTRIP_NOT_VERIFIED','editableRoundtrip','A successful editable save/reload is required')
    if readback.get('sceneReopened')is not True:
        issue('SCENE_ROUNDTRIP_NOT_VERIFIED','sceneReopened','Saved scene reopen is required')
    for field,expected in (('importPlanSha256',expected_plan_sha256),
                           ('sourceManifestSha256',expected_source_manifest_sha256)):
        if expected is not _UNSET and (not isinstance(expected,str)or re.fullmatch(r'[0-9a-f]{64}',expected)is None
                or readback.get(field)!=expected):
            issue('NATIVE_READBACK_PLAN_IDENTITY_INVALID',field,'Saved observation must match the current owned import plan and source manifest pins')
    native={}
    rows=readback.get('nativeFiles')
    if not isinstance(rows,list)or not rows:
        issue('NATIVE_FILE_INVENTORY_INVALID','nativeFiles','A nonempty saved native file inventory is required')
    else:
        for index,row in enumerate(rows):
            path=row.get('path')if isinstance(row,dict)else None
            digest=row.get('sha256')if isinstance(row,dict)else None
            valid_path=(isinstance(path,str)and path.startswith('Assets/')and '\\'not in path
                and not any(part in ('','.','..')for part in path.split('/'))
                and not PurePosixPath(path).is_absolute())
            if (not valid_path or path in native or not isinstance(digest,str)
                    or re.fullmatch(r'[0-9a-f]{64}',digest)is None):
                issue('NATIVE_FILE_INVENTORY_INVALID',f'nativeFiles[{index}]','Unique canonical Assets path and lowercase SHA256 required')
                continue
            native[path]=digest
    return dict(valid=not issues,issues=issues,nativeFiles=native,
                scope='resource-gallery'if gallery else'saved-source-node-subset')
