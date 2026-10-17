# R0-5090-004：真实WSL固定OPI最小导入通过

- 证据类型：USER_PASTED_WSL_TERMINAL_OUTPUT；协调端未远程执行。
- 接收记录时间：2026-10-17T12:47:36Z，不是远端运行时间。
- 用户终端：DESKTOP-B5PNBNC的Ubuntu，目录 `/home/tingfeng/LongPIBench-Reproduction`。
- 接收时协调端main：95128323061b71589bdc53dcf0f4a15889a9f29f；用户此次粘贴未含协调仓库HEAD，不能将其认定为远端实际HEAD。
- 用户称为下载项目已临时公开协作仓库；这是用户自述，未在本次回执中验证GitHub可见性。公开读取不证明远端具有push权限。

## 已确认

LongPIBench恢复到c7b80114ae56f65fb8019ec82afdb3df91e4ed65，OPI恢复到fbed5cca347488f88363790ae3ae97c56116da6a；最小loader输出DataSentinelDetector、PromptLocate及Pinned OPI core import: PASS。四个关键源文件哈希与锁定值一致，记录CRLF_to_LF策略及唯一绝对导入改相对导入变换，method_behavior_modified=false。源码根目录位于真实WSL用户目录。

这与此前GPU合成、依赖导入成功回执共同构成环境与代码导入准备证据。此次没有创建模型实例，gpu_load_verified=false是正确范围声明，没有运行检测定位或目标推理。

## 剩余及接续

任务004仅待完整环境清单保存与可追溯路径/哈希，尚不标COMPLETED。任务005可并行接续清单保存、固定数据恢复及HF配置元数据访问检查。模型权重加载、spaCy en_core_web_sm、adapter下载与DataSentinel checkpoint选择仍未验收；不进入正式实验。
