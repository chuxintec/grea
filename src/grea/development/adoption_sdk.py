"""Hash-bound, consumer-authored SDK migration intent for adoption.

The supported v1 surface is deliberately narrow: canonical paths, exact
after-image importer settings, identity-preserving replacements, and explicit
serialized-object checks/maps. PE inspection is delegated to managed_metadata.
"""

import re

from .adoption_assemblies import importer_roles
from .errors import fail
from .io import encoded, load, read, safe, sha
from .managed_metadata import inspect_managed
from .owned_fs import RootReader

CONTRACT = "beaver-sdk-migration/1"
GUID = re.compile(r"^[a-f0-9]{32}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
MVID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SPEC_NODES = 500_000


def _hash(value, where):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        fail("ADOPT_SDK_SPEC", where, "Expected lowercase SHA256")
    return value


def _path(value, where, suffix=None):
    if (not isinstance(value, str) or not value.startswith("Assets/") or "\\" in value or ":" in value
            or any(x in ("", ".", "..") for x in value.split("/"))
            or suffix and not value.lower().endswith(suffix)):
        fail("ADOPT_SDK_SPEC", where, "Expected canonical Assets-relative path")
    return value


def _version(value, where):
    if not isinstance(value, list) or len(value) != 4 or any(type(x) is not int or x < 0 for x in value):
        fail("ADOPT_SDK_SPEC", where, "Expected a four-part nonnegative assembly version")
    return value


def _local_id(value, where):
    if type(value) is not int or value == 0 or value < -(1 << 63) or value > (1 << 63) - 1:
        fail("ADOPT_SDK_SPEC", where, "Expected a nonzero signed 64-bit Unity local ID")
    return value


def load_spec(path, expected_sha256):
    if path is None:
        if expected_sha256 is not None:
            fail("ADOPT_SDK_SPEC", "expectedSdkMigrationSha256", "Hash requires an SDK migration spec")
        return None
    if expected_sha256 is None:
        fail("ADOPT_SDK_SPEC", "expectedSdkMigrationSha256", "An explicit SDK migration SHA256 is required")
    path = safe(path); raw = read(path, 4 * 1024 * 1024); digest = sha(raw)
    if digest != _hash(expected_sha256, "expectedSdkMigrationSha256"):
        fail("ADOPT_SDK_SPEC_DRIFT", str(path), "Explicit SDK migration spec SHA256 differs")
    doc = load(raw, max_nodes=SPEC_NODES)
    required = {"schemaVersion", "contract", "unityVersion", "candidateManifestSha256", "targetAssetsSha256", "referenceCoverage", "licenses", "assemblies", "references"}
    if (not isinstance(doc, dict) or set(doc) not in (required,required|{"retainedInactiveAssemblies"}) or type(doc.get("schemaVersion")) is not int
            or doc["schemaVersion"] != 1 or doc.get("contract") != CONTRACT):
        fail("ADOPT_SDK_SPEC", str(path), "Expected closed beaver-sdk-migration/1 spec")
    if doc["unityVersion"] != "6000.6.2f1": fail("ADOPT_SDK_SPEC",str(path),"This implementation supports Unity 6000.6.2f1 only")
    if doc["referenceCoverage"]!="all-sdk-references-in-adopted-assets": fail("ADOPT_SDK_SPEC",str(path),"Schema v1 requires a complete adopted-asset reference inventory")
    return path, doc, digest


def _read_candidate(root, files, path, digest, where):
    row = files.get(path)
    if not row or row.get("sha256") != digest:
        fail("ADOPT_SDK_SOURCE_DRIFT", path, f"{where} is absent from the frozen candidate or has another hash")
    with RootReader(root) as view: raw = view.read(path, max_bytes=64 * 1024 * 1024)
    if sha(raw) != digest: fail("ADOPT_SDK_SOURCE_DRIFT", path, "Candidate changed during validation")
    return raw


def _read_target(root, files, path, digest, where):
    row = files.get(path)
    if not row or row.get("sha256") != digest:
        fail("ADOPT_SDK_TARGET_DRIFT", path, f"{where} differs from the pinned target inventory")
    with RootReader(root) as view: raw = view.read(path, max_bytes=64 * 1024 * 1024)
    if sha(raw) != digest: fail("ADOPT_SDK_TARGET_DRIFT", path, "Target changed during validation")
    return raw


def _metadata(raw, name, version, where):
    try: observed = inspect_managed(raw)
    except (ValueError, UnicodeError) as error:
        fail("ADOPT_SDK_IDENTITY", where, f"Bounded managed assembly inspection failed: {error}")
    if observed["name"].casefold() != name.casefold() or observed["version"] != version:
        fail("ADOPT_SDK_IDENTITY", where, "Assembly name/version differs from the explicit spec")
    module_version_id=observed.get("moduleVersionId")
    if not isinstance(module_version_id,str) or not MVID.fullmatch(module_version_id):
        fail("ADOPT_SDK_IDENTITY",where,"Bounded managed metadata did not provide a canonical Module MVID")
    return observed


def _types(value, observed, where):
    if not isinstance(value, list) or not value:
        fail("ADOPT_SDK_TYPES", where, "Expected an explicit complete CLR TypeDef inventory")
    out = []; names=set()
    for index, item in enumerate(value):
        if not isinstance(item, str): fail("ADOPT_SDK_TYPES", f"{where}[{index}]", "TypeDefs must be full-name strings")
        name=item
        if not isinstance(name,str) or not name or name in names:
            fail("ADOPT_SDK_TYPES", f"{where}[{index}]", "Type names must be unique nonempty CLR full names")
        names.add(name)
        out.append(name)
    if names != set(observed["types"]):
        fail("ADOPT_SDK_TYPES", where, "Spec must enumerate every TypeDef exactly")
    return sorted(out)


def validate_spec(spec_path, expected_sha256, incoming, manifest_sha256, files, target, target_files):
    loaded=load_spec(spec_path, expected_sha256)
    if loaded is None: return None
    path, doc, spec_sha=loaded
    inventory_sha=sha(encoded(target_files))
    if doc["candidateManifestSha256"] != manifest_sha256 or doc["targetAssetsSha256"] != inventory_sha:
        fail("ADOPT_SDK_SPEC_STALE", str(path), "Candidate manifest or target Assets baseline differs from the reviewed spec")
    licenses=[]; license_ids=set()
    if not isinstance(doc["licenses"],list) or not doc["licenses"]:
        fail("ADOPT_SDK_SPEC", "licenses", "At least one exact license notice is required")
    for i, row in enumerate(doc["licenses"]):
        where=f"licenses[{i}]"
        if not isinstance(row,dict) or set(row)!={"id","root","path","sha256"} or row["root"] not in ("candidate","target"):
            fail("ADOPT_SDK_SPEC",where,"Expected exact license id/root/path/sha256")
        if not isinstance(row["id"],str) or not row["id"] or row["id"] in license_ids:
            fail("ADOPT_SDK_SPEC",where,"License IDs must be unique")
        license_ids.add(row["id"]); p=_path(row["path"],where); h=_hash(row["sha256"],where)
        if row["root"]=="candidate": _read_candidate(incoming,files,p,h,"License notice")
        else: _read_target(target,target_files,p,h,"License notice")
        licenses.append(dict(id=row["id"],root=row["root"],path=p,sha256=h))

    if not isinstance(doc["assemblies"],list) or not doc["assemblies"] or not isinstance(doc["references"],list):
        fail("ADOPT_SDK_SPEC",str(path),"Expected SDK role pairs and explicit serialized references")
    pairs=[]; source_paths=set(); target_paths=set(); pair_roles=set(); assembly_names=set(); script_types={}
    for i,pair in enumerate(doc["assemblies"]):
        where=f"assemblies[{i}]"
        if not isinstance(pair,dict) or set(pair)!={"role","assemblyName","licenseId","monoScriptPolicy","variants"}:
            fail("ADOPT_SDK_SPEC",where,"Expected exact role/assemblyName/licenseId/monoScriptPolicy/variants")
        if not isinstance(pair["role"],str) or not pair["role"] or pair["licenseId"] not in license_ids:
            fail("ADOPT_SDK_SPEC",where,"SDK role must bind a declared license")
        if pair["role"] in pair_roles: fail("ADOPT_SDK_SPEC",where,"SDK role identifiers must be unique")
        pair_roles.add(pair["role"])
        if pair["monoScriptPolicy"] not in ("capture-before-preserve-and-pair-localids","capture-before-preserve-and-attest-inactive-player"):
            fail("ADOPT_SDK_SPEC",where,"Unsupported native MonoScript evidence policy")
        name=pair["assemblyName"]
        if not isinstance(name,str) or not name or not isinstance(pair["variants"],list) or len(pair["variants"])!=2:
            fail("ADOPT_SDK_SPEC",where,"Schema v1 requires a complete Editor/Player pair")
        if name.casefold() in assembly_names: fail("ADOPT_SDK_SPEC",where,"A managed assembly identity may have only one role pair")
        assembly_names.add(name.casefold())
        normalized=[]; domains=set()
        for j,v in enumerate(pair["variants"]):
            vwhere=f"{where}.variants[{j}]"
            fields={"domain","action","path","after","before"}
            if not isinstance(v,dict) or set(v)!=fields or v["domain"] not in ("editor","player") or v["domain"] in domains:
                fail("ADOPT_SDK_SPEC",vwhere,"Expected one distinct Editor and Player variant")
            domains.add(v["domain"])
            if v["action"] not in ("add","reuse","replace-preserve-guid"):
                fail("ADOPT_SDK_SPEC",vwhere,"Unsupported canonical migration action")
            p=_path(v["path"],vwhere,".dll")
            if p in source_paths or p in target_paths: fail("ADOPT_SDK_SPEC",p,"DLL path appears more than once")
            source_paths.add(p);target_paths.add(p)
            after=v["after"]
            if not isinstance(after,dict) or set(after)!={"guid","sha256","metaSha256","version","culture","publicKeySha256","metadataTypes"}:
                fail("ADOPT_SDK_SPEC",vwhere,"Expected exact candidate after-image")
            if not isinstance(after["guid"],str) or not GUID.fullmatch(after["guid"]): fail("ADOPT_SDK_SPEC",p,"Invalid after GUID")
            file_hash=_hash(after["sha256"],p); meta_hash=_hash(after["metaSha256"],p); version=_version(after["version"],p)
            raw=_read_candidate(incoming,files,p,file_hash,"SDK DLL")
            meta_raw=_read_candidate(incoming,files,p+".meta",meta_hash,"SDK importer metadata")
            from .adoption import identity
            if identity(meta_raw,"Assets")!=after["guid"]: fail("ADOPT_SDK_IDENTITY",p+".meta","After GUID differs from the canonical spec")
            expected_role=[v["domain"]]
            if importer_roles(meta_raw)!=expected_role: fail("ADOPT_SDK_ROLE",p+".meta","Candidate importer after-image is not exactly the declared domain")
            info=_metadata(raw,name,version,p)
            if after["culture"]!=info["culture"] or after["publicKeySha256"]!=info["publicKeySha256"]:
                fail("ADOPT_SDK_IDENTITY",p,"Declared culture/public-key identity differs from bounded metadata")
            metadata_types=_types(after["metadataTypes"],info,p+".metadataTypes")
            before=v["before"]
            if v["action"]=="add":
                if before is not None or p in target_files or p+".meta" in target_files:
                    fail("ADOPT_SDK_TARGET_DRIFT",p,"Add variant must have no target before-image")
                before_norm=None
            else:
                if not isinstance(before,dict) or set(before)!={"guid","sha256","metaSha256","version","culture","publicKeySha256","roles","metadataTypes"}:
                    fail("ADOPT_SDK_SPEC",vwhere,"Reuse/replace requires a complete pinned target before-image")
                if not isinstance(before["guid"],str) or not GUID.fullmatch(before["guid"]) or before["guid"]!=after["guid"]:
                    fail("ADOPT_SDK_IDENTITY",p,"Canonical replacement must preserve its exact target GUID")
                old_hash=_hash(before["sha256"],p); old_meta_hash=_hash(before["metaSha256"],p+".meta"); old_version=_version(before["version"],p)
                old_raw=_read_target(target,target_files,p,old_hash,"SDK before-image")
                old_meta=_read_target(target,target_files,p+".meta",old_meta_hash,"SDK importer before-image")
                if identity(old_meta,"Assets")!=before["guid"]: fail("ADOPT_SDK_IDENTITY",p+".meta","Pinned before GUID differs")
                old_roles=importer_roles(old_meta)
                if old_roles is None:
                    text=old_meta.decode('utf-8','strict')
                    if 'PluginImporter:' in text or 'platformData:' in text or before["roles"]!=["native-required"]:
                        fail("ADOPT_SDK_ROLE",p+".meta","Unsupported before importer must be captured by the native Editor explicitly")
                    old_roles=["native-required"]
                elif not isinstance(before["roles"],list) or before["roles"]!=old_roles:
                    fail("ADOPT_SDK_ROLE",p+".meta","Before importer role differs from its exact native serialization")
                old_info=_metadata(old_raw,name,old_version,p)
                if before["culture"]!=old_info["culture"] or before["publicKeySha256"]!=old_info["publicKeySha256"]:
                    fail("ADOPT_SDK_IDENTITY",p,"Pinned before culture/public-key identity differs from bounded metadata")
                old_metadata_types=_types(before["metadataTypes"],old_info,p+".before.metadataTypes")
                if v["action"]=="reuse" and (old_hash!=file_hash or old_meta_hash!=meta_hash):
                    fail("ADOPT_SDK_SPEC",p,"Reuse requires identical canonical before/after bytes")
                before_norm=dict(guid=before["guid"],sha256=old_hash,metaSha256=old_meta_hash,version=old_version,culture=old_info["culture"],publicKeySha256=old_info["publicKeySha256"],moduleVersionId=old_info["moduleVersionId"],roles=old_roles,metadataTypes=old_metadata_types)
            normalized.append(dict(pairRole=pair["role"],domain=v["domain"],action=v["action"],path=p,after=dict(guid=after["guid"],sha256=file_hash,metaSha256=meta_hash,version=version,culture=info["culture"],publicKeySha256=info["publicKeySha256"],moduleVersionId=info["moduleVersionId"],roles=expected_role,metadataTypes=metadata_types),before=before_norm,name=info["name"],publicTypes=sorted(info["publicTypes"])))
            for type_name in metadata_types:
                script_types[(after["guid"],type_name)]=(v["domain"],pair["role"])
        if domains!={"editor","player"}: fail("ADOPT_SDK_SPEC",where,"Exactly one Editor and one Player role is required")
        editor_before=next(variant["before"] for variant in normalized if variant["domain"]=="editor")
        player_after=next(variant["after"] for variant in normalized if variant["domain"]=="player")
        if editor_before is None and any(variant["before"] is not None for variant in normalized):
            fail("ADOPT_SDK_MVID_UNKNOWN",where,"A prior Player image cannot be bound without the canonical Editor before-image MVID")
        if pair["monoScriptPolicy"]=="capture-before-preserve-and-attest-inactive-player":
            if editor_before is None or player_after["sha256"]!=editor_before["sha256"] or player_after["moduleVersionId"]!=editor_before["moduleVersionId"]:
                fail("ADOPT_SDK_MVID_UNKNOWN",where,"Inactive Player attestation requires exact Player-after/Editor-before DLL bytes and MVID")
        pairs.append(dict(role=pair["role"],assemblyName=name,licenseId=pair["licenseId"],monoScriptPolicy=pair["monoScriptPolicy"],variants=normalized))

    retained_inactive=None;retained_guids=set();retained_paths=set()
    if "retainedInactiveAssemblies" in doc:
        block=doc["retainedInactiveAssemblies"]
        if not isinstance(block,dict) or set(block)!={"policy","assemblies"} or block["policy"]!="preserve-exact-disabled-target-assemblies" or not isinstance(block["assemblies"],list) or not block["assemblies"]:
            fail("ADOPT_SDK_SPEC","retainedInactiveAssemblies","Expected explicit preserve-exact-disabled-target-assemblies policy and nonempty rows")
        retained_inactive=[]
        for i,row in enumerate(block["assemblies"]):
            where=f"retainedInactiveAssemblies.assemblies[{i}]"
            fields={"path","guid","sha256","metaSha256","assemblyName","moduleVersionId","roles"}
            if not isinstance(row,dict) or set(row)!=fields or row["roles"]!=[]:
                fail("ADOPT_SDK_SPEC",where,"Expected closed exact disabled DLL pin with roles=[]")
            p=_path(row["path"],where,".dll")
            if p in retained_paths or p in target_paths or p in source_paths or p in files or p+".meta" in files:
                fail("ADOPT_SDK_SPEC",p,"Inactive DLL must be a unique unchanged target-only path")
            retained_paths.add(p)
            if not isinstance(row["guid"],str) or not GUID.fullmatch(row["guid"]) or row["guid"] in retained_guids:
                fail("ADOPT_SDK_SPEC",p,"Inactive DLL GUID must be valid and unique")
            retained_guids.add(row["guid"])
            file_hash=_hash(row["sha256"],p);meta_hash=_hash(row["metaSha256"],p+".meta")
            mvid=row["moduleVersionId"]
            if not isinstance(mvid,str) or not MVID.fullmatch(mvid) or not isinstance(row["assemblyName"],str) or not row["assemblyName"]:
                fail("ADOPT_SDK_SPEC",p,"Inactive DLL requires exact assembly identity and canonical MVID")
            raw=_read_target(target,target_files,p,file_hash,"Retained inactive SDK DLL")
            meta_raw=_read_target(target,target_files,p+".meta",meta_hash,"Retained inactive SDK importer")
            from .adoption import identity
            if identity(meta_raw,"Assets")!=row["guid"]:
                fail("ADOPT_SDK_IDENTITY",p+".meta","Retained inactive GUID differs from its exact meta")
            if importer_roles(meta_raw)!=[]:
                fail("ADOPT_SDK_ROLE",p+".meta","Retained inactive importer is not proven disabled on every serialized platform")
            try: observed=inspect_managed(raw)
            except (ValueError,UnicodeError) as error:
                fail("ADOPT_SDK_IDENTITY",p,f"Retained inactive managed metadata inspection failed: {error}")
            if observed["name"].casefold()!=row["assemblyName"].casefold() or observed.get("moduleVersionId")!=mvid:
                fail("ADOPT_SDK_IDENTITY",p,"Retained inactive assembly name/MVID differs from exact target DLL bytes")
            canonical_editors=[variant for pair in pairs for variant in pair["variants"]
                if variant["domain"]=="editor" and pair["assemblyName"].casefold()==observed["name"].casefold()
                and variant["after"]["sha256"]==file_hash and variant["after"]["moduleVersionId"]==mvid]
            if len(canonical_editors)!=1:
                fail("ADOPT_SDK_INACTIVE_SOURCE",p,"Retained inactive DLL must be byte/MVID-identical to one declared canonical Editor after-image")
            if canonical_editors[0]["before"] is None:
                fail("ADOPT_SDK_INACTIVE_SOURCE",p,"Retained inactive source requires a pinned canonical Editor before-image for every transaction phase")
            retained_inactive.append(dict(path=p,guid=row["guid"],sha256=file_hash,metaSha256=meta_hash,assemblyName=observed["name"],moduleVersionId=mvid,roles=[],canonicalEditorPath=canonical_editors[0]["path"]))

    references=[]; seen=set(); reference_assets={}
    for i,row in enumerate(doc["references"]):
        where=f"references[{i}]"; fields={"root","assetPath","assetSha256","objectLocalId","propertyPath","action","source","canonical"}
        if not isinstance(row,dict) or set(row)!=fields or row["root"] not in ("candidate","target"):
            fail("ADOPT_SDK_SPEC",where,"Invalid serialized-reference pin")
        p=_path(row["assetPath"],where); h=_hash(row["assetSha256"],p)
        _local_id(row["objectLocalId"],where+".objectLocalId")
        if not isinstance(row["propertyPath"],str) or not row["propertyPath"]:
            fail("ADOPT_SDK_SPEC",where,"Reference must identify an exact object and property")
        if row["action"] not in ("preserve","map") or row["action"]=="map" and row["root"]!="candidate":
            fail("ADOPT_SDK_SPEC",where,"Only incoming serialized references may be mapped")
        if row["action"]=="map" and row["propertyPath"]=="m_Script":
            fail("ADOPT_SDK_REFERENCE","m_Script","Schema v1 never rewrites serialized script identities")
        inv=files if row["root"]=="candidate" else target_files; root=incoming if row["root"]=="candidate" else target
        asset_key=(row["root"],p,h)
        if asset_key not in reference_assets:
            if row["root"]=="candidate": _read_candidate(root,inv,p,h,"Serialized object asset")
            else: _read_target(root,inv,p,h,"Serialized object asset")
            reference_assets[asset_key]=(row["root"],p,h)
        key=(row["root"],p,row["objectLocalId"],row["propertyPath"])
        if key in seen: fail("ADOPT_SDK_REFERENCE",p,"Reference object/property is duplicated")
        seen.add(key)
        def parse_ref(value,label):
            if not isinstance(value,dict) or set(value)!={"guid","localId","type"} or not isinstance(value["guid"],str) or not GUID.fullmatch(value["guid"]) or not isinstance(value["type"],str) or not value["type"]:
                fail("ADOPT_SDK_SPEC",where+"."+label,"Expected exact GUID/localID/type")
            _local_id(value["localId"],where+"."+label+".localId")
            return dict(guid=value["guid"],localId=value["localId"],type=value["type"])
        source=parse_ref(row["source"],"source"); canonical=parse_ref(row["canonical"],"canonical")
        if row["root"]=="candidate" and (source["guid"] in retained_guids or canonical["guid"] in retained_guids):
            fail("ADOPT_SDK_REFERENCE",where,"Incoming SDK references cannot target a retained inactive duplicate")
        if row["action"]=="map" and (source["guid"] in retained_guids or canonical["guid"] in retained_guids):
            fail("ADOPT_SDK_REFERENCE",where,"Reference maps cannot target a retained inactive duplicate")
        if row["action"]=="preserve" and source!=canonical: fail("ADOPT_SDK_REFERENCE",where,"Preserve must keep exact GUID/localID/type")
        if row["action"]=="map" and source==canonical: fail("ADOPT_SDK_REFERENCE",where,"Map must specify an actual explicit identity change")
        if row["propertyPath"]=="m_Script":
            if row["action"]!="preserve" or source["type"] not in [name for guid,name in script_types if guid==source["guid"]]:
                fail("ADOPT_SDK_REFERENCE",where,"m_Script must preserve a declared native assembly type; localID is confirmed by Unity during execution")
        references.append(dict(root=row["root"],assetPath=p,assetSha256=h,objectLocalId=row["objectLocalId"],propertyPath=row["propertyPath"],action=row["action"],source=source,canonical=canonical))
    # Recheck each unique serialized asset once after traversing the full spec.
    # Large prefab bytes must not be rehashed once per object/property row.
    for root_name,p,h in reference_assets.values():
        if root_name=="candidate": _read_candidate(incoming,files,p,h,"Serialized object asset final check")
        else: _read_target(target,target_files,p,h,"Serialized object asset final check")
    normalized=dict(path=str(path),sha256=spec_sha,candidateManifestSha256=manifest_sha256,
                targetAssetsSha256=sha(encoded(target_files)),referenceCoverage=doc["referenceCoverage"],licenses=licenses,assemblies=pairs,references=references)
    if retained_inactive is not None:
        normalized["retainedInactiveAssemblies"]=dict(policy="preserve-exact-disabled-target-assemblies",assemblies=retained_inactive)
    return normalized
