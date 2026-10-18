# 本机大文件位置：用户明确偏好

用户2026-10-18（Asia/Tokyo）明确要求永久记住：这台电脑不把大文件下载到C盘，全部放D/E盘。已通过记忆扩展便签保存；模型、数据、安装包、大型环境、缓存和下载临时文件均适用。

本项目的模型权重与试跑venv已经位于E:\LongPIBench\ingress_detection_pilot。后续通用大缓存使用E:\Caches；storage_paths.ps1会设置HF Hub/assets/xet/datasets、Transformers、Torch和pip路径，并为当前下载进程设置E盘TEMP/TMP。-Persist仅持久化当前用户的库缓存变量；不修改所有Windows应用的TEMP/TMP。以后下载前仍需显式加载此脚本，不能仅凭最终模型位置在E盘就忽略缓存/临时副本。

## 本轮本机认证核验

核验只检查是否存在，不读取/显示任何token内容：HF_TOKEN环境变量不存在，HUGGING_FACE_HUB_TOKEN环境变量不存在，默认活动token文件不存在。这表明本机默认HF配置尚未登录；不代表浏览器账号未获Prompt Guard权限。先前401来自匿名请求，不能单凭它推断必须重新申请模型权限。

浏览器登录状态和本机HF凭据是两套状态。已有网页权限时，可用同一个账号的read token在本地huggingface-cli login交互输入，然后只读验证固定config访问。token不要贴进聊天或命令行参数。登录本身不下载模型权重；小型认证文件不随大型缓存迁移。

## 既有C盘缓存

实际pip cache info显示C:\Users\Admin\AppData\Local\pip\cache约4103 MB HTTP缓存（另约1 MB wheels）。其包含既有缓存，不能全部归为本次试跑新增。自动审批拒绝了“复制、校验后递归删除源缓存”的提议，理由是用户要求后续存储位置，未明确授权删除既有缓存；命令未执行。已改用仅配置未来路径的安全替代，旧缓存不复制、不删除，不绕过审批。

本轮未重跑检测器、未改原始分数、R0–R4或已完成统计结论。需要日后清理旧缓存时，应另获用户明确指令。
