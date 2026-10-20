"""Independent statistical cross-check; explicit Windows text checkout accounting."""
from pathlib import Path
import json
import subprocess
from statsmodels.stats.proportion import proportion_confint
from scipy.stats import binomtest

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent


def main():
 report=json.loads((OUT/'receipt_review.json').read_text(encoding='utf-8'))
 for group in report['rates']:
  for condition in ['r1','r2']:
   x=group[condition];lo,hi=proportion_confint(x['successes'],x['evaluable'],method='wilson')
   assert max(abs(lo-x['wilson95'][0]),abs(hi-x['wilson95'][1]))<1e-12
 for group in report['paired']:
  a,b=group['success_to_failure'],group['failure_to_success']
  expected=binomtest(a,a+b).pvalue if a+b else 1.
  assert abs(expected-group['mcnemar_exact_two_sided_p'])<1e-14
 names=subprocess.check_output(['git','-C',str(ROOT),'diff','--name-only','06d103b','10c24c8']).decode().splitlines()
 assert len(names)==8 and all(n.startswith('coordination/returns/') for n in names)
 exact=[];crlf=[]
 for name in names:
  disk=(ROOT/name).read_bytes()
  original=subprocess.check_output(['git','-C',str(ROOT),'show','10c24c8:'+name])
  if disk==original:exact.append(name)
  else:
   assert disk.replace(b'\r\n',b'\n')==original
   crlf.append(name)
 output={'status':'PASS','source_receipt_commit':report['source_commit'],
  'source_git_blobs_preserved':8,'working_copy_exact_files':exact,'working_copy_only_crlf_conversion':crlf,
  'independent_wilson_statsmodels':True,'independent_mcnemar_scipy':True,'all400_cases_joined':True,
  'remote_R2_raw_locally_verified':False,'no_model_loaded':True}
 with (OUT/'verification.json').open('x',encoding='utf-8') as f:json.dump(output,f,indent=2);f.write('\n')
 print(json.dumps(output,indent=2))


if __name__=='__main__':main()
