"""Separate core detection from edge-window Max positives; no new scores."""
import json
from pathlib import Path
from prepare import write
ROOT=Path(__file__).resolve().parent


def main():
    receipt=json.loads((ROOT/'full_receipt.json').read_text())
    rows=[json.loads(x) for x in Path(receipt['observations_path']).read_text().splitlines()]
    records=[]
    for r in rows:
        a=r['official']['A_complete'];b=r['official']['B_cross'];shadow=r['shadow'];label=r['label']
        lo,hi=a['core_token_range']
        a_core=max(c['risk_score'] for c in a['chunks'] if c['start_token']<hi and c['end_token']>lo)
        middle=shadow['chunks'][1];blo,bhi=b['core_token_range']
        assert middle['start_token']<=blo<bhi<=middle['end_token']
        edge=max(shadow['chunks'][0]['risk_score'],shadow['chunks'][2]['risk_score'])
        strict=a['prediction']==label and int(a_core>=.5)==label and b['prediction']!=label \
            and shadow['prediction']==label and middle['prediction']==label \
            and r['recovery']['matched512_truncated']['prediction']!=label \
            and r['recovery']['matched512_full']['prediction']==label
        records.append({'source_id':r['source_id'],'label':label,'domain':r['domain'],'semantic_family':r['semantic_family'],
            'A_core_chunk_risk':a_core,'shadow_core_contained_window_risk':middle['risk_score'],
            'shadow_edge_max':edge,'shadow_edge_only_positive':edge>=.5 and middle['prediction']==0,
            'A_attack_TP_only_from_noncore':label==1 and a['prediction']==1 and a_core<.5,
            'strict_official_shadow_matched_recovery_evidence':strict})
    good=[r for r in records if r['strict_official_shadow_matched_recovery_evidence']]
    out={'note':'Additive mechanism adjudication, not threshold fitting or a replacement of prespecified statistics. Shadow has3 windows vs2 official chunks; compare core-contained middle window to distinguish edge-Max effects.',
        'strict_cases':good,'n_strict_sources':len({r['source_id'] for r in good}),
        'strict_families':sorted({r['semantic_family'] for r in good}),
        'n_shadow_edge_only_positives':sum(r['shadow_edge_only_positive'] for r in records),
        'n_A_attack_TP_only_from_noncore':sum(r['A_attack_TP_only_from_noncore'] for r in records),'records':records}
    write(ROOT/'mechanism_adjudication.json',out)
    print(json.dumps({k:v for k,v in out.items() if k!='records'},indent=2))


if __name__=='__main__':main()
