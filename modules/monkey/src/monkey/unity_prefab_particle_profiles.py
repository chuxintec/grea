"""Bounded, explicit native storage mapping; source IR is never rewritten."""
from copy import deepcopy

from .sources.compiled import fail

PROFILE = 'ParticleSystem-Bounce-Constant-disabled-2021.3.30f1-to-6000.6.2f1-v2'
PREFIX = 'CollisionModule.m_Bounce'


def bounce_constant_profile(obj, source_versions, target_version, fields):
    if obj.get('type') != 'ParticleSystem' or 'm_Bounce' not in obj.get('data', {}).get('CollisionModule', {}):
        return fields, None
    if obj.get('classId') != 198 or source_versions != ['2021.3.30f1'] or target_version != '6000.6.2f1':
        fail('UNITY_PREFAB_PARTICLE_PROFILE_VERSION', obj.get('sourceObjectId', '$'), 'Exact builtin/source/target profile required')
    collision = obj['data']['CollisionModule']
    bounce = collision['m_Bounce']
    numeric_one = lambda v: type(v) in (int, float) and v == 1
    if (type(collision.get('enabled')) not in (bool, int) or collision['enabled'] != 0
            or type(bounce.get('minMaxState')) is not int or bounce['minMaxState'] != 0
            or not numeric_one(bounce.get('scalar')) or not numeric_one(bounce.get('minScalar'))
            or any(not isinstance(bounce.get(k), dict) or bounce[k].get('m_Curve') != []
                   for k in ('maxCurve', 'minCurve'))):
        fail('UNITY_PREFAB_PARTICLE_PROFILE_CONDITION', obj.get('sourceObjectId', '$'),
             'Only disabled Collision/Bounce Constant1 with two empty source curves is covered')
    replacements = {PREFIX + '.minScalar': 0.0, PREFIX + '.maxCurve.m_Curve.Array.size': 2}
    result = []
    found = set()
    for field in fields:
        row = deepcopy(field)
        if row['path'] in replacements:
            expected_kind = 'float' if row['path'].endswith('.minScalar') else 'integer'
            value_key = 'floatValue' if expected_kind == 'float' else 'intValue'
            expected_source = 1 if expected_kind == 'float' else 0
            if row['path'] in found or row['kind'] != expected_kind or row.get(value_key) != expected_source:
                fail('UNITY_PREFAB_PARTICLE_PROFILE_FIELDS', row['path'], 'Flattened source field differs from source data')
            found.add(row['path'])
            value_key = 'floatValue' if row['kind'] == 'float' else 'intValue'
            row.update(mapping=PROFILE, sourcePath=row['path'], sourceExpected=str(row[value_key]))
            row[value_key] = replacements[row['path']]
        result.append(row)
    if found != set(replacements):
        fail('UNITY_PREFAB_PARTICLE_PROFILE_FIELDS', '$', 'Source fields for explicit representation mapping are absent')
    for index in range(2):
        for key, value in dict(time=float(index), value=0.0, inSlope=0.0, outSlope=0.0,
                               tangentMode=0, weightedMode=0,
                               inWeight=0.3333333432674408, outWeight=0.3333333432674408).items():
            kind = 'integer' if type(value) is int else 'float'
            result.append(dict(path=f'{PREFIX}.maxCurve.m_Curve.Array.data[{index}].{key}',
                               kind=kind, **{'intValue' if kind == 'integer' else 'floatValue': value},
                               mapping=PROFILE, sourcePath=PREFIX + '.maxCurve.m_Curve',
                               sourceExpected='[];native-default-keys-inactive-in-Constant-mode'))
    mapping = dict(profile=PROFILE, sourceObjectId=obj['sourceObjectId'], sourceRawSha256=obj['rawSha256'],
                   sourceUnityVersions=source_versions, targetUnityVersion=target_version,
                   sourceCollisionEnabled=collision['enabled'], sourceBounce=deepcopy(bounce),
                   targetPublicConstant=1, targetMode=0, targetScalar=1, targetMinScalar=0,
                   targetMaxCurveKeyCount=2, targetMaxCurveValues=[0, 0], targetMinCurveKeyCount=0,
                   comparison='explicit-native-representation;not-raw-equality',
                   semanticBasis='Constant mode/value inference;source-runtime-not-executed',
                   boundary='Collision stays disabled;other source fields/curves/references remain strict')
    return result, mapping
