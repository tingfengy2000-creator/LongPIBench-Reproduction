"""Reviewable M2 figures; representative cases chosen by frozen order, not effect size."""
import json
from pathlib import Path
import textwrap
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from prepare import write

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]


def main():
    receipt=json.loads((ROOT/'full_receipt.json').read_text())
    rows=[json.loads(x) for x in Path(receipt['observations_path']).read_text().splitlines()]
    matrices=json.loads((ROOT/'transition_matrices.json').read_text())
    plan=json.loads((ROOT/'plan.json').read_text())
    inputs={(r['source_id'],r['label']):r for r in map(json.loads,(REPO/plan['frozen_inputs_path']).read_text().splitlines())}
    out=ROOT/'figures';out.mkdir(exist_ok=False)
    plt.rcParams.update({'font.size':10,'axes.titlesize':11})
    fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    colors={'email':'#2b6f9c','resume':'#c66b28'}
    conds=['A_complete','B_cross','C_tail']
    for label,ax in zip([0,1],axs[0]):
        for r in rows:
            if r['label']==label:ax.plot(range(3),[r['official'][c]['risk_score'] for c in conds],color=colors[r['domain']],alpha=.35,marker='o',ms=2)
        ax.axhline(.5,color='firebrick',ls='--',lw=1)
        ax.set_xticks(range(3),['A: complete','B: cross','C: tail']);ax.set_ylim(-.02,1.02)
        ax.set_ylabel('Official document Max risk')
        ax.set_title(('Benign' if label==0 else 'Attack')+'; 40 paired source variants')
        ax.legend(handles=[Patch(color=v,label=k) for k,v in colors.items()],fontsize=8)
    conditions=['core_reference']+conds
    for label,color,name,shift in [(0,'#ad3e3e','FP',-.18),(1,'#535ea6','FN',.18)]:
        counts=[sum(r['label']==label and r['official'][c]['prediction']!=label for r in rows) for c in conditions]
        axs[1,0].bar(np.arange(4)+shift,counts,width=.35,label=name,color=color)
    axs[1,0].set_xticks(range(4),['Core ref','A','B','C']);axs[1,0].set_ylim(0,42);axs[1,0].legend()
    axs[1,0].set_title('Official path errors; each class n=40');axs[1,0].set_ylabel('Error count')
    recovery=['native_truncated','native_partial16','native_full','matched512_truncated','matched512_partial16','matched512_full']
    for label,color,name,shift in [(0,'#ad3e3e','FP',-.18),(1,'#535ea6','FN',.18)]:
        counts=[sum(r['label']==label and r['recovery'][c]['prediction']!=label for r in rows) for c in recovery]
        axs[1,1].bar(np.arange(6)+shift,counts,width=.35,label=name,color=color)
    axs[1,1].set_xticks(range(6),['Native\ntrunc','Native\n+16','Native\nfull','512\ntrunc','512\n+16','512\nfull'])
    axs[1,1].set_ylim(0,42);axs[1,1].legend();axs[1,1].set_title('Recovery diagnostic errors; NOT deployment metrics')
    axs[1,1].set_ylabel('Inherited-label error count')
    fig.suptitle('M2: 40 authored sources, paired benign/attack; fixed threshold 0.5')
    fig.savefig(out/'paired_risk_and_errors.png',dpi=180);plt.close(fig)
    fig,axs=plt.subplots(2,2,figsize=(9,8),layout='constrained')
    for i,label in enumerate([0,1]):
        for j,mode in enumerate(['native','matched512']):
            mat=np.array(matrices[f'{mode}_truncated_to_full_label{label}'])
            ax=axs[i,j];ax.imshow(mat,vmin=0,vmax=40,cmap='Blues')
            for a in [0,1]:
                for b in [0,1]:ax.text(b,a,str(mat[a,b]),ha='center',va='center',fontsize=20,color='white' if mat[a,b]>20 else 'black')
            ax.set_xticks([0,1],['0: pass','1: flag']);ax.set_yticks([0,1],['0: pass','1: flag'])
            ax.set_xlabel('Full context prediction');ax.set_ylabel('Truncated prediction')
            ax.set_title(f'{mode}; '+('benign' if label==0 else 'attack')+' n=40')
    fig.suptitle('Context recovery transitions: all sources, including new errors')
    fig.savefig(out/'recovery_transitions.png',dpi=180);plt.close(fig)
    chosen=[]
    for label in [0,1]:
        eligible=sorted([r for r in rows if r['label']==label and r['official']['A_complete']['prediction']==label and r['official']['B_cross']['prediction']!=label],key=lambda r:r['source_id'])
        if eligible:chosen.append(eligible[0])
    excerpts=[]
    fig,axs=plt.subplots(max(1,len(chosen)),2,figsize=(12,max(4,4*len(chosen))),squeeze=False,layout='constrained')
    if not chosen:
        axs[0,0].text(.1,.5,'No official A-correct / B-wrong case.',transform=axs[0,0].transAxes)
        axs[0,1].axis('off')
    for i,r in enumerate(chosen):
        inp=inputs[r['source_id'],r['label']]
        for y,c in enumerate(conds):
            doc=r['official'][c];lo,hi=doc['core_token_range'];a,b=doc['target_token_range']
            axs[i,0].barh(y,hi-lo,left=lo,height=.4,color='#4c91bd')
            axs[i,0].barh(y,b-a,left=a,height=.18,color='#c64b41')
        axs[i,0].axvline(512,color='black',ls='--');axs[i,0].set_xlim(0,1024);axs[i,0].set_yticks(range(3),['A','B','C'])
        axs[i,0].set_xlabel('Whole document token offset');axs[i,0].set_title(r['source_id']+' / '+r['variant'])
        labels=['Core','A','B','C','Shadow','Trunc','Full']
        values=[r['official']['core_reference']['risk_score']]+[r['official'][c]['risk_score'] for c in conds]+[r['shadow']['risk_score'],r['recovery']['native_truncated']['risk_score'],r['recovery']['native_full']['risk_score']]
        axs[i,1].bar(range(len(values)),values,color=['#777777']*4+['#b2783a']*3)
        axs[i,1].axhline(.5,color='firebrick',ls='--');axs[i,1].set_ylim(0,1.02);axs[i,1].set_xticks(range(len(values)),labels)
        axs[i,1].set_ylabel('Risk; last 3 are diagnostics');axs[i,1].set_title('Lexicographically first eligible case per label')
        excerpts.append({'source_id':r['source_id'],'label':r['label'],'domain':r['domain'],'text_type':r['text_type'],
            'selection':'First source_id among official A-correct/B-wrong for each label; not max effect',
            'core_text':inp['core_text'],'core_cut_token':inp['core_cut'],'core_token_ids':inp['core_token_ids'],
            'original_full_input_hash':inp['documents']['B_cross']['input_sha256'],
            'official':{c:{'core_token_range':r['official'][c]['core_token_range'],'target_token_range':r['official'][c]['target_token_range'],
                'chunk_scores':r['official'][c]['chunk_scores'],'prediction':r['official'][c]['prediction']} for c in conds}})
    fig.suptitle('Representative boundary cases; synthetic and exploratory, not causal proof')
    fig.savefig(out/'boundary_cases.png',dpi=180);plt.close(fig)
    write(ROOT/'representative_cases.json',excerpts)
    print(json.dumps({'figures':3,'representative_cases':len(chosen)}))


if __name__=='__main__':main()
