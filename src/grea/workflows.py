"""Unity-specific routing; a plan does not stand in for execution evidence."""
from .common import package_root

WORKFLOWS = {
 'recover': {'title':'完整恢复/首次重建','baseline':'同版本、同状态的原版资源与实际运行','dimensions':['rules','runtime','visual'], 'steps':[(1,['unpack_xapk','video_manifest','video_sheet']),(2,['assetripper','unity_dependency_audit']),(12,['ilspy','cpp2il','il2cppdumper','ghidra']),(3,['unity_asset_ledger']),(8,[])], 'boundary':'静态提取可以独立继续；缺原生运行证据时不关闭动态一致性。'},
 'fix': {'title':'局部一致性修复','baseline':'相关原版依据与受影响入口','dimensions':['rules','runtime'], 'steps':[(4,[]),(5,[]),(6,['compare_traces']),(7,['compare_events']),(8,[])], 'boundary':'按具体缺口选专题，不重新完整解包或无条件做性能基准。'},
 'reskin': {'title':'授权换皮','baseline':'最新批准设计与已授权玩法/交互不变量','dimensions':['runtime','visual'], 'steps':[(21,['image_alpha_audit']),(5,[]),(7,[]),(8,[])], 'boundary':'已批准素材直接复用；指定制作工具依当前会话能力，不自动收费生图或审批。'},
 'refactor': {'title':'结构重构/UI迁移','baseline':'当前工程行为、GUID/fileID、动态加载键','dimensions':['identity','runtime'], 'steps':[(20,['unity_asset_ledger']),(17,['unity_dependency_audit']),(18,[]),(8,[])], 'boundary':'UI框架迁移仅在本次要求时进行；不凭未引用列表删除资产。'},
 'performance': {'title':'性能优化','baseline':'同设备、场景、输入、随机和负载的前后结果','dimensions':['performance','rules','runtime'], 'steps':[(22,[]),(8,[])], 'boundary':'不通过改变随机、限帧或画质制造收益；不冒称已验证目标渠道。'},
 'deliver': {'title':'构建/预览/发布','baseline':'源码/资产/构建ID与目标平台','dimensions':['identity','platform'], 'steps':[(23,['verify_payload_tree']),(8,[])], 'boundary':'默认Mac；只进入本次已授权的预览、安装或发布环节。'},
 'maintain': {'title':'工具/技能/复盘维护','baseline':'调用契约、文档、兼容入口与必要测试','dimensions':['identity'], 'steps':[(9,['check_grea_skill']),(15,[])], 'boundary':'不启动无关游戏、收费服务或Git推送。'},
}

def plan(mode,source_engine='unity'):
    value=WORKFLOWS[mode]
    refs=package_root()/'skill/references'
    steps=[{'reference':str(next(refs.glob(f'{n}-*.md'))),'tool_ids':tools,'executed':False} for n,tools in value['steps']]
    if source_engine!='unity' and mode in ('recover','fix'):
        steps.insert(0,{'reference':str(next(refs.glob('14-*.md'))),'tool_ids':['laya_contract_audit'] if source_engine=='laya' else [],'executed':False})
    preferred={'unity_dependency_audit':'audit_unity_dependencies','unity_asset_ledger':'snapshot_unity_assets','compare_traces':'compare_gameplay_traces','audit_numeric_texture':'inspect_numeric_texture'}
    for step in steps:step['grea_operations']=[preferred[x] for x in step['tool_ids'] if x in preferred]
    return {'mode':mode,'title':value['title'],'baseline':value['baseline'],'required_dimensions':value['dimensions'],'steps':steps,'boundary':value['boundary'],'source_engine':source_engine,'executed':False}
