# PIGuard固定源码审查（加载前）

对象：`leolee99/PIGuard@dd78b24e330193a22d2293ac66922dd4f982f563`。

允许执行的唯一自定义推理模块是`modeling_piguard.py`，SHA256=`5be806a223cf20c418171a409726110c02a7377d75f22ee6f80d7c72ac0fa529`。已逐行阅读完整973字节源码并与config.auto_map核对：只导入torch、Transformers DeBERTa配置/分类类及SequenceClassifierOutput；定义配置类，继承DeBERTa分类器，将分类头设为Linear(hidden_size,num_labels)，使用deberta最后隐藏状态的第0位置生成logits；注册自动类。没有网络、文件写入、shell、动态eval/exec或额外下载调用。

需要attention_mask；风险分量由固定config的0=benign、1=injection确定，softmax(class1)是模型类别分数，不宣称为校准恶意概率。

同revision中的其他脚本也已阅读，但**不执行**：

- `__init__.py`仍引用旧injecguard模块，不使用其package入口，也不修历史源码。
- `inference_examples.py`与`load_model.py`会按浮动repo加载并使用truncation，不能直接作为长文档B0入口。
- `save_model.py`包含本地torch.load与保存操作，是开发辅助脚本，不是本轮推理依赖。

运行方式：新建B0独立venv与进程，使用只读路径复用已验收CPU依赖，所有模型与动态模块缓存放E盘；从固定snapshot的本地目录执行经过摘要核对的auto_map模块，local_files_only=True。该安排隔离环境写入，不宣称是操作系统安全沙箱。模型以safetensors加载，不运行pickle权重。

PG1无需自定义代码。PG2本机固定配置访问403，尚未取得可执行自定义源码，不能假定无需源码审查；若远端取得auto_map，先回传审查，不自动trust_remote_code。
