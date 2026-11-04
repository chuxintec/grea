# 源组件与原生验证结果

Unity 与 Creator 的 `componentCoverage` 按完整 `plan.components` 逐项列出 `native`、`retained`、`disabled`、`unsupported`、`missing`；`convertible` 不再缩小分母。原生身份必须来自实际保存回读，静态字段、保留数据及源可见内容另需相应证据。源和原生诊断均保留在结果中。

- `staticValidation` 只检查拥有文件、GUID、资源与目录完整性。
- `nativeStaticValidation` 检查全源组件的原生身份及字段；未验证或仅保留的组件不能汇总为完整通过。
- `retentionValidation` 单列身份、字段、原始资源的保留结果。
- `staticPresentationValidation` 单列源可见内容的原生静态呈现证据。非渲染 Spine 或未证明的自定义 UI 静态语义仍是 partial。
- `visualValidation`、业务和 Player 均需要独立执行证据。Editor 导入、保存、回读或截图不产生 Player 执行证明；当前这条验证链的 `runtimeCheck` 与 `playerValidation` 为 `not_run`。

`freeze-native-selection` 接受导入器的干净 `imported` 枚举，同时继续核对固定回读 SHA、原生文件、重开、全源覆盖和静态呈现。它不接收缺失分母、未完成呈现或被过滤后的原生诊断来代替这些门槛。已验证静态部分的明确纯动态边界仍单列。

静态 Spine 续接会在模板及每个平铺实例上创建真实类型载体，再由既有 Prefab 替换链复制字段、替换引用；同类型 Spine 组件按精确模板来源身份对应。它保留骨骼、atlas、原始纹理页和材料对象引用，尚未实现 Spine 渲染或动画。

自定义 Unity UI schema carrier 的字段型 C# 声明不是原程序集完整方法清单。缺少独立原始方法来源时，即使目标原生基类能绘制，也不证明源类的渲染或生命周期语义已恢复。

引擎版本常量摘要是声明的参考 pin，不能自证实际引擎文件身份；实际源 pack、shader 阶段、脚本、资源及 SDK 字节仍按各自来源核验。63 位参考摘要已统一到规范 64 位定义，未接线历史 helper 的独立来源问题不被此修改宣称解决。
