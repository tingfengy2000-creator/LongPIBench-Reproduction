"""Author requested Markdown from validated real-score artifacts only."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import sys

ROOT=Path(__file__).resolve().parent


def percent(x): return 'NA' if x is None else f'{100*x:.2f}%'


def main():
    summary=json.loads((ROOT/'pilot_results.json').read_text(encoding='utf-8'))
    summary['provenance']={
        'upstream_commit':'c7b80114ae56f65fb8019ec82afdb3df91e4ed65',
        'dataset_revision':'cdfdfdba8838911ec3d120d5bbf584c0afb280f2',
        'analysis_source_sha256':hashlib.sha256((ROOT/'analyze_scores.py').read_bytes()).hexdigest(),
        'analysis_python':sys.version,
        'analysis_packages':{k:importlib.metadata.version(k) for k in ['numpy','scipy','matplotlib']},
        'note':'Inference ran at the recorded input commit; analysis worktree source is bound by SHA256. Generated summary enriched during report authoring; raw scores and original scorer outputs unchanged.'}
    completions={}
    rows_by_model={}
    for alias,result in summary['detectors'].items():
        completion=json.loads((ROOT/f'results/{alias}/completion.json').read_text())
        completions[alias]=completion
        result['model_repo']=completion['model_repo'];result['model_revision']=completion['model_revision']
        result['inference_input_commit']=completion['input_commit']
        rows_by_model[alias]=[json.loads(l) for l in (ROOT/f'results/{alias}/pilot_real_scores.jsonl').read_text().splitlines()]
    (ROOT/'pilot_results.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')

    lines=['# H1长度诊断：真实小样本工程验证','',
        '本轮完成两套检测器各80份输入，共40独立源文档；非正式论文实验。分数不是攻击概率。所有运行配置/版本见environment_audit.md，样本与split见sample_manifest.jsonl，原logits/softmax见各results目录。', '',
        '**结论：观察到了聚合排序变化和明显的领域差异；尚未建立可排除领域混杂的长度误报机制，长度条件Max没有优于公平校准的Max。两模型均未通过推理前写入pilot_plan.json的H1支持门槛，不能将此解释为已经证明长度完全无影响。**','',
        '## 校准与开发留出', '',
        '每域20个源文档各有clean/attack，前12源（按预声明hash顺序）作校准、后8源作开发留出。每模型仅24良性校准样本用于阈值；开发留出16良性+16攻击。schema中的test不表示新的正式论文测试集，所有源均与原R0–R4公开全集重叠。没有使用留出标签重新调阈值。', '',
        '每方法独立校准；全部校准FP=2/24（8.33%，经验预算≤10%），并非只拿默认0.5当竞争对手。下表报告开发留出实际FPR，不能将不同实际FPR的TPR直接称为固定FPR收益。', '',
        '| 检测器 | 方法 | TP | FP | TN | FN | TPR | 实际FPR |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for alias,result in summary['detectors'].items():
        for method,detail in result['methods'].items():
            m=detail['development_holdout_overall']
            lines.append(f"| {alias} | {method} | {m['tp']} | {m['fp']} | {m['tn']} | {m['fn']} | {percent(m['tpr'])} | {percent(m['fpr'])} |")
    lines+=['','## 分域混淆矩阵','',
        '每行只有8份良性、8份攻击，FPR分辨率12.5个百分点。DeBERTa四方法总体与分域计数相同，不表示其完整排序处处相同。', '',
        '| 检测器 | 方法 | 域 | TP | FP | TN | FN | TPR | FPR |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for alias,result in summary['detectors'].items():
        for method,detail in result['methods'].items():
            for domain,m in detail['development_holdout_by_domain'].items():
                lines.append(f"| {alias} | {method} | {domain} | {m['tp']} | {m['fp']} | {m['tn']} | {m['fn']} | {percent(m['tpr'])} | {percent(m['fpr'])} |")
    lines+=['','## 长度相关与领域混杂','',
        '以下只用每域20份真实良性文档；pooled为两域40份。Spearman相关以3999次固定seed置换给双侧p值，分域效应小样本且没有额外确认集。门槛在推理前声明：同一检测器两个域都正相关、各p≤0.025且均有聚合排序倒置。该保守门槛未过并不证明零效应；置换数不是新增样本数。', '',
        '| 检测器 | 域 | n | Max与Token长度rho | 置换p | Max与Chunk数rho | 默认阈值良性FP | Max/Top-2倒置对数 |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for alias,result in summary['detectors'].items():
        for domain,d in result['length_associations'].items():
            t=d['benign_score_vs_tokens'];c=d['benign_score_vs_chunks']
            rho='NA（Chunk数常量）' if c['rho'] is None else f"{c['rho']:.3f}"
            lines.append(f"| {alias} | {domain} | {d['benign_n']} | {t['rho']:.3f} | {t['permutation_two_sided_p']:.5f} | {rho} | {d['default_fp']}/{d['benign_n']} | {d['max_top2_rank_inversions']} |")
    lines+=['',
        '合并两域的相关性强，但Email长且分数高、Resume短且分数低/略低；分域后Email相关接近零，不能把pooled趋势解释为长度导致误报。DeBERTa全部20份良性Resume均为单Chunk，其token相关即使为正，也不支持“块数增多导致Max多重误报”的机制。', '',
        'DistilBERT按官方LABEL_1解释在全部40份良性上默认FP=40/40；因此默认FPR已到上限，没有可识别的长度递增误报梯度。其配置没有SAFE/INJECTION语义映射，不能从本轮自行反转标签极性；报告只针对官方启发式口径。', '',
        '**可核查的排序变化实例**：DistilBERT的resume-088-clean有514 tokens，块长512与2，原分数分别0.9995698333和0.0005049873；Max≈0.99957，Top-2≈0.50004。仅一个极短尾块就使该文档在本域Top-2排名显著降低。其20份良性Resume的19对Max/Top-2倒置均涉及这个唯一的双块文档；这不能充当普遍长度校准收益，也没有证明短尾块是误判的因果来源。', '',
        '## 长度覆盖与分数分布','',
        '下面的范围/分位数合并校准与开发留出，仅描述输入覆盖与分数，**不是留出性能表**；score均为文档Max。分桶在推理前固定，不按分数挑桶。完整数值见pilot_results.json的score_distributions。', '',
        '| 检测器 | 域 | 标签 | 字段/范围 | n | 最小 | Q25 | 中位 | Q75 | 最大 | 默认阳性 |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for alias,result in summary['detectors'].items():
        for d in result['score_distributions']:
            lines.append(f"| {alias} | {d['domain']} | {d['label']} | {d['field']} {d['range']} | {d['n']} | {d['score_min']:.7g} | {d['score_q25']:.7g} | {d['score_median']:.7g} | {d['score_q75']:.7g} | {d['score_max']:.7g} | {d['default_positive']} |")
    lines+=['','## 置信限制与固定FPR口径','',
        'DeBERTa Max的总体TPR=8/16，Wilson 95%区间约[28.00%,72.00%]；FPR=1/16，区间约[1.11%,28.33%]。DistilBERT Max的FPR=3/16，区间约[6.59%,43.01%]。各域即便0/8误报，其95% Wilson上界仍约32.44%，不能据此宣称部署FPR稳定≤5%或≤10%。所有方法/域的区间均保存在JSON中。', '',
        'DeBERTa各方法实际运行点同为TPR50%、FPR6.25%；长度校准未改善该点。DistilBERT Max/长度Max实际FPR18.75%，Top-2/Q90为12.5%，均超过探索预算；不能把降低拒绝率或不同实际FPR下的TPR描述为胜出。', '',
        '16份良性留出不能恰好得到10% FPR。另给描述性ROC包络：在留出FPR≤10%范围内，DeBERTa Max/Top-2的TPR包络56.25%，Q90/长度Max为50%；DistilBERT Max18.75%、Top-2/Q90为25%、长度Max12.5%。这些是同一开发留出排序的事后描述，不是据此重新选出的部署阈值，更不是正式TPR@FPR保证。', '',
        '长度校准邻域取24份良性中的20份，且p值离散。DeBERTa长度方法LOO校准FP=2，但含自身回放时FP=1；不能将二者混称同一校准结果。原脚本nextafter与严格>的浮点保守性、官方>=.5比较符差异详见score_schema.md。', '',
        '## 曲线与来源','',
        '![真实长度散点与开发留出ROC](figures/length_and_roc.png)','',
        '![真实良性文档聚合排序](figures/rank_changes.png)','',
        '![域内长度诊断，独立纵轴缩放](figures/within_domain_length_zoom.png)','',
        'ROC圆点是预先用校准集锁定的运行点；曲线只用于描述性排序。PDF副本同目录，原数值曲线在results/*/roc_points.json。', '',
        '来源：固定LongPIBench c7b80114ae56f65fb8019ec82afdb3df91e4ed65；数据cdfdfdba8838911ec3d120d5bbf584c0afb280f2；推理输入commit 06c0f476dc1771864773d6aad2d3ed50fa5b8f4f。DeBERTa @90c9989b1a342275dd0d1a95aad283c04e075671；DistilBERT @c5da1fefd33c98c447b50dd806fe86aeb9e8c26c。CPU FP32/512不重叠块/原官方0.5判定和独立校准的聚合阈值。每模型80输入、40源；非正式论文实验。']
    with (ROOT/'length_diagnostics.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
    verdict='''# Go / No-Go：工程可行，方法主张暂不放行

**结论：工程验证GO；长度校准性能提升及多尺度/疑难区域复核开发NO-GO（证据不足，不是证明长度效应不存在）。** 本轮不训练、不实现新防御，也不提交多尺度或复核器下一阶段方案。

## 已观测的失败模式

1. **默认阈值和标签语义风险**：DistilBERT按官方LABEL_1风险映射，将40/40良性全部判阳性；标签语义缺少模型config的显式证明。保留原行为，未反转类别。经公平校准后，其开发留出FPR仍12.5%–18.75%，不能宣称已控制在10%。
2. **领域与长度混杂**：合并Email/Resume时分数随长度增大，但域内关联弱且不一致；DeBERTa的良性Resume全部单块。不能把域间差异归因于Max块数效应。
3. **短尾块可显著改变聚合排序**：DistilBERT单个514-token Resume的2-token尾块，使Top-2排名变化很大。观察到排序变化，不等于检测质量变好；还没有位置/边界控制实验验证机制。
4. **校准未带来可支持的收益**：DeBERTa四方法开发留出计数完全相同（TP8/FP1/TN15/FN8），DistilBERT长度Max也与Max同一混淆矩阵（TP8/FP3/TN13/FN8）。不能写LCMD有效或优于原算法。

## 置信限制

每检测器80输入来自40源，每域只有8份良性和8份攻击开发留出；同源clean/attack成对，不是80个独立源。各域FPR每次变化12.5个百分点，0/8误报的Wilson 95%上界仍约32.44%。整体16份良性留出也不足以精确比较10%，更不能做5% FPR论文结论。

本轮test字段只是开发留出，全部源与R0–R4公开复现全集重叠。不能把本次分组包装为新的未见正式测试，也没有按分数重新挑样本或阈值。长度近邻只从24份良性里取20份，区分能力弱；原脚本只是离线工程比较器，不具备部署FPR保证。

Prompt Guard仍未运行：本机匿名受保护配置401，Owner明确要求先完成两公开模型。本轮没有假设5090账号已获该模型权限，也未用随机/FAKE分数补齐。没有运行下游LLM，不能报告新方案的ASR、合法任务可用性或端到端安全收益。

## 当前决策

保留完整真实分数和负面结果，停止将长度校准当作已证实贡献。若后续继续研究，应先补充领域内独立良性文档与更广长度覆盖、核实DistilBERT语义标签，再预先冻结新的分割和判定口径；这属于证据补足，不是获准开发多尺度或复核方法。达到支持门槛前，不为复杂方案写正向有效性结论。

数据/版本/样本量：LongPIBench c7b80114ae56f65fb8019ec82afdb3df91e4ed65；数据cdfdfdba8838911ec3d120d5bbf584c0afb280f2；DeBERTa @90c9989b1a342275dd0d1a95aad283c04e075671、DistilBERT @c5da1fefd33c98c447b50dd806fe86aeb9e8c26c；推理commit 06c0f476dc1771864773d6aad2d3ed50fa5b8f4f；各80输入/40源，CPU FP32，512不重叠块。所有结果为工程验证，非正式论文实验。原脚本输出、独立核验、混淆矩阵和图见pilot_results.json、method_metrics.csv、length_diagnostics.md及results/。
'''
    with (ROOT/'go_no_go.md').open('x',encoding='utf-8') as f:f.write(verdict)


if __name__=='__main__':main()
