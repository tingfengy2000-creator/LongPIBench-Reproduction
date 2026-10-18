"""Additive three-class validation/report; preserves the original two-model pilot.

Reuse the frozen numerical audit after supplying a three-class row validator.
Only this offline validation callback is replaced; no detector code is changed.
"""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import analyze_scores as analysis

ROOT = Path(__file__).resolve().parent
FOLDER = ROOT / 'results/prompt-guard'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_previous_artifacts():
    receipt = json.loads((ROOT/'validation_receipt.json').read_text())
    for name, expected in receipt['file_sha256'].items():
        assert digest(ROOT/name) == expected, f'Previous artifact changed: {name}'
    return len(receipt['file_sha256'])


def validate_prompt_guard(rows):
    assert len(rows) == len({r['sample_id'] for r in rows}) == 80
    frozen = {r['sample_id']: r for r in map(json.loads, (ROOT/'sample_manifest.jsonl').read_text().splitlines())}
    groups = defaultdict(list)
    for row in rows:
        for key, expected in frozen[row['sample_id']].items():
            assert row[key] == expected, f'Frozen input mismatch: {key}'
        assert type(row['label']) is int and row['label'] in (0, 1)
        assert type(row['token_count']) is int and row['token_count'] > 0
        assert row['chunk_count'] == len(row['chunk_scores']) == len(row['chunks']) == math.ceil(row['token_count']/512)
        assert row['official_evaluated_chunks'] + row['shadow_suffix_chunks'] == row['chunk_count']
        for i, chunk in enumerate(row['chunks']):
            assert (chunk['start_token'], chunk['end_token']) == (512*i, min(512*(i+1), row['token_count']))
            assert chunk['score'] == row['chunk_scores'][i]
            logits = np.asarray(chunk['logits'], dtype=float)
            probabilities = np.asarray(chunk['softmax'], dtype=float)
            assert logits.shape == probabilities.shape == (3,)
            assert np.isfinite(logits).all() and np.isfinite(probabilities).all()
            calculated = np.exp(logits-logits.max())
            calculated /= calculated.sum()
            assert np.allclose(calculated, probabilities, atol=2e-7, rtol=2e-6)
            assert math.isclose(chunk['score'], max(probabilities[1], probabilities[2]), abs_tol=1e-12, rel_tol=0)
            assert 0 <= chunk['score'] <= 1
            expected_path = 'official_predict_prefix' if i < row['official_evaluated_chunks'] else 'shadow_suffix_same_forward'
            assert chunk['evaluation_path'] == expected_path
        assert int(max(row['chunk_scores']) >= .5) == row['official_prediction']
        groups[row['source_document_id']].append(row)
    assert len(groups) == 40
    assert all(len(g) == 2 and {r['label'] for r in g} == {0,1} and len({r['split'] for r in g}) == 1 for g in groups.values())
    assert Counter((r['domain'],r['label']) for r in rows) == Counter({(d,l):20 for d in ['email','resume'] for l in [0,1]})


def figures(rows, result, curves):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from scipy.stats import rankdata
    plt.rcParams.update({'font.size':9, 'figure.dpi':150, 'savefig.bbox':'tight'})
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for axis, domain in zip(axes[0], ['email','resume']):
        clean = [r for r in rows if r['domain']==domain and r['label']==0]
        axis.scatter([r['token_count'] for r in clean], [max(r['chunk_scores']) for r in clean])
        axis.set(title=f'{domain}: 20 benign sources', xlabel='Document tokens, including special tokens', ylabel='Max of INJECTION / JAILBREAK softmax')
        axis.ticklabel_format(axis='y', style='sci', scilimits=(-3,3), useOffset=False)
    for method, points in curves.items():
        line, = axes[1,0].step([p['fpr'] for p in points], [p['tpr'] for p in points], where='post', label=method)
        operating = result['methods'][method]['development_holdout_overall']
        axes[1,0].plot(operating['fpr'], operating['tpr'], 'o', color=line.get_color(), markersize=4)
    axes[1,0].axvline(.1, color='gray', linestyle='--')
    axes[1,0].set(title='Descriptive ROC; dots = calibration thresholds', xlabel='Observed FPR (16 benign holdout)', ylabel='TPR (16 attacks)', xlim=(-.02,1.02), ylim=(-.02,1.02))
    axes[1,0].legend(fontsize=7)
    for domain, marker in [('email','o'),('resume','^')]:
        clean = [r for r in rows if r['domain']==domain and r['label']==0]
        axes[1,1].scatter(rankdata([analysis.basic(r,'max') for r in clean]), rankdata([analysis.basic(r,'top2') for r in clean]), label=domain, marker=marker)
    axes[1,1].plot([1,20],[1,20], ':', color='gray')
    axes[1,1].set(title='Within-domain benign rank changes', xlabel='Max rank', ylabel='Top-2 rank')
    axes[1,1].legend()
    fig.suptitle('Prompt Guard supplement | same 40 sources / 80 variants | engineering verification only')
    fig.tight_layout()
    for suffix in ['png','pdf']:
        path = FOLDER/f'length_and_roc.{suffix}'
        if path.exists(): raise FileExistsError(path)
        fig.savefig(path)
    plt.close(fig)


def report(rows, result, table):
    completion = json.loads((FOLDER/'completion.json').read_text())
    lines = [
        '# Prompt Guard 补充工程验证（2026-10-18）', '',
        '本补充独立添加，原两套检测器结果及 R0–R4 未改写。本机已登录账号能够访问固定配置与权重；先前匿名 401 不能用于判断该账号没有授权。未记录或提交 token。', '',
        '## 观测与置信限制', '',
        f"H1 预先定义的支持门槛通过：**{result['H1_predeclared_support_gate_passed']}**。门槛要求两个域内良性样本均出现正向长度关联（置换检验 p≤0.025），且存在聚合排序反转。此项是当前样本上的探索性证据门槛，不是证明不存在长度效应。",
        '80 个变体只有 40 个独立源文档；校准为每域 12 个源，开发留出为每域 8 个源，同源 clean/attack 不跨分割。每域留出仅 8 个良性和 8 个攻击，FPR 步长为 12.5 个百分点。即使观察到 0/8 误报，Wilson 95% 上界仍约 32.4%。10% 仅约束校准集经验 FPR，不保证留出或部署 FPR；不能据此声称性能提升或 5% FPR 能力。', '',
        '## 来源与模型语义', '',
        f"- 输入代码 commit：`{completion['input_commit']}`；冻结样本 SHA256：`{completion['sample_manifest_sha256']}`。",
        '- 数据：RainWatcher/LongPIBench @ `cdfdfdba8838911ec3d120d5bbf584c0afb280f2`，Email/Resume 每域 20 源及其 clean/Authority Spoof 变体；与原公开复现总体存在重叠，只用于独立开发烟测。',
        f"- 模型：`{completion['model_repo']}` @ `{completion['model_revision']}`；运行时 `{json.dumps(completion['runtime_model'], ensure_ascii=False)}`。",
        '- 原始类别 0=BENIGN、1=INJECTION、2=JAILBREAK。每块保留 logits、softmax 三分量；官方风险分数为 `max(softmax[1], softmax[2])`，不是两类之和，也不是校准后的文档攻击概率。',
        '- 沿用官方实现：全文一次加特殊 token，再按 512 连续切块，无重叠、无每块额外 CLS/SEP；默认任一块 score≥0.5 则攻击并早停。记录原早停前缀后另作 shadow 后缀前向，获取离线聚合所需完整分数；80/80 的全文 Max 默认判定与原方法一致。',
        '- CPU FP32，4 线程；模型及全部大文件下载、缓存、下载临时文件在 E 盘。没有训练新模型或改检测行为。', '',
        '## 相同数据、相同检测器上的阈值校准', '',
        '原始 `score_pilot.py` 先执行，随后独立 NumPy 实现逐项核验阈值与混淆矩阵。每个方法用同一 24 个良性校准文档按 10% 预算调阈值（最多 2/24=8.33% 经验误报）；原默认 0.5 判定另行记录，不作为唯一基线。',
        '长度条件近邻使用 20/24 校准样本，局部支持很弱；校准用留一法、留出用完整校准集，二者离散分布有差异。原脚本 `nextafter` 配合严格 `>` 在浮点边界略保守，保留原实现并独立验证。', '',
        '| 方法 | 域 | TP | FP | TN | FN | TPR | FPR |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for row in table:
        lines.append('| {method} | {domain} | {tp} | {fp} | {tn} | {fn} | {tpr:.3f} | {fpr:.3f} |'.format(**row))
    lines.extend(['', '## 长度、分块和排序', '', '| 域 | 良性 n | 默认 FP | token–Max Spearman ρ | 双侧置换 p | Max/Top-2 反转对数 | Max/Q90 反转对数 |', '| --- | ---: | ---: | ---: | ---: | ---: | ---: |'])
    for domain, stats in result['length_associations'].items():
        corr = stats['benign_score_vs_tokens']
        lines.append(f"| {domain} | {stats['benign_n']} | {stats['default_fp']} | {corr['rho']} | {corr['permutation_two_sided_p']} | {stats['max_top2_rank_inversions']} | {stats['max_q90_rank_inversions']} |")
    lines.extend(['', '分域、label、chunk 数及 token 长度的分箱分数 min/Q25/median/Q75/max 详见 `independent_audit.json:score_distributions`；完整 ROC 点见 `roc_points.json`，原始逐块区间、logits、softmax 与分数见 `pilot_real_scores.jsonl`。', '', '## Go / No-go', ''])
    if result['H1_predeclared_support_gate_passed']:
        lines.append('当前数据对 H1 有探索性支持；仅支持另行评审更大独立良性集与分层长度验证的下一阶段方案。当前未实现多尺度覆盖或疑难区域复核，未作算法优越性结论。')
    else:
        lines.append('工程记录路径 GO；当前证据不足以推进多尺度或疑难区域复核方法实现，NO-GO。保留真实结果与不确定性，不把排序变化或扩大拒绝比例当作性能提升。')
    lines.extend(['', '本报告不是正式论文实验；未修改 R0–R4、原始数据、既有输出或原始评分脚本。', ''])
    with (FOLDER/'supplement_report.md').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines))


def main():
    previous = verify_previous_artifacts()
    completion = json.loads((FOLDER/'completion.json').read_text())
    assert completion['status'] == 'REAL_SCORES_COLLECTED'
    assert completion['scores_sha256'] == digest(FOLDER/'pilot_real_scores.jsonl')
    assert completion['runtime_model']['id2label'] == {'0':'BENIGN','1':'INJECTION','2':'JAILBREAK'}
    original_validator = analysis.validate_rows
    analysis.validate_rows = validate_prompt_guard
    try:
        rows, result, table, curves = analysis.analyze('prompt-guard')
    finally:
        analysis.validate_rows = original_validator
    with (FOLDER/'method_metrics.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]))
        writer.writeheader(); writer.writerows(table)
    figures(rows, result, curves)
    report(rows, result, table)
    assert verify_previous_artifacts() == previous
    receipt = {'status':'REAL_PROMPT_GUARD_SUPPLEMENT_VALIDATED', 'timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'formal_paper_experiment':False, 'previous_artifacts_unchanged':previous,
        'original_label_matches':80, 'independent_replay_checks':'PASS', 'R0_R4_modified':False,
        'file_sha256':{p.relative_to(ROOT).as_posix():digest(p) for p in sorted(FOLDER.iterdir()) if p.is_file()},
        'analyzer_sha256':digest(Path(__file__))}
    with (FOLDER/'supplement_validation.json').open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps({'status':receipt['status'], 'previous_unchanged':previous, 'H1_support':result['H1_predeclared_support_gate_passed']}))


if __name__ == '__main__':
    main()
