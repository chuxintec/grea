"""Explicit lifecycle metadata; stage selection is not execution permission."""
from .common import GreaError
STAGES=('research','recover','reskin','develop','iterate','release','operate')
WORK_MODES=('faithful','reskin','feature','tuning','prototype','operate')
DELIVERY=('report','candidate','native_project','playable','release_candidate','operations_preview')
DEFAULTS={'research':('research','faithful'),'assess':('research','faithful'),'evidence':('recover','faithful'),'recover':('recover','faithful'),'port':('recover','faithful'),'fix':('iterate','faithful'),'reskin':('reskin','reskin'),'evolve':('iterate','tuning'),'feature':('develop','feature'),'tuning':('iterate','tuning'),'prototype':('develop','prototype'),'operate':('operate','operate'),'deliver':('release','faithful'),'refactor':('iterate','faithful'),'performance':('iterate','tuning'),'maintain':('iterate','faithful')}
CHANGE_MODES=('reskin','evolve','feature','tuning','prototype')

def metadata(mode,lifecycle_stage=None,work_mode=None,delivery_level=None):
    stage,work=DEFAULTS[mode];stage=lifecycle_stage or stage;work=work_mode or work
    if stage not in STAGES or work not in WORK_MODES or delivery_level is not None and delivery_level not in DELIVERY:
        raise GreaError('INVALID_LIFECYCLE','Unsupported lifecycle metadata')
    if mode in ('recover','port','fix','evidence') and work!='faithful':
        raise GreaError('MODE_CONFLICT','Faithful recovery does not add new rules; select a declared change mode.')
    if mode in ('feature','tuning','prototype','reskin','operate') and work!=DEFAULTS[mode][1]:
        raise GreaError('MODE_CONFLICT','Workflow and declared work mode disagree.')
    allowed={'faithful':set(STAGES)-{'reskin','operate'},'reskin':{'reskin','iterate','release'},'feature':{'develop','iterate','release'},'tuning':{'develop','iterate','release'},'prototype':{'develop','iterate'},'operate':{'operate'}}
    if stage not in allowed[work]:raise GreaError('STAGE_CONFLICT','Stage is inconsistent with work mode.')
    return dict(lifecycle_stage=stage,work_mode=work,delivery_level=delivery_level or ('report' if stage=='research' else 'operations_preview' if work=='operate' else 'candidate'))

def check_change(mode,contract,meta):
    if contract is not None and mode not in CHANGE_MODES:raise GreaError('INVALID_CHANGE_CONTRACT','Select an explicit change workflow.')
    if contract and contract['schema_version']==2:
        if contract['scope']!=meta['work_mode']:raise GreaError('MODE_CONFLICT','Change scope and workflow disagree.')
    elif contract and (mode in ('feature','tuning','prototype') or meta['work_mode'] not in ('reskin','tuning')):
        raise GreaError('INVALID_CHANGE_CONTRACT','New rule/feature workflows require a v2 contract.')
