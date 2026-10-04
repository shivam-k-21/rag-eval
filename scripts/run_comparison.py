"""Run BM25 and expanded BM25 with identical cases, model, K and support judge."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rag_eval.cli import main as evaluate
ROOT=Path(__file__).resolve().parent.parent

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--generator',choices=['extractive','groq'],default='extractive')
    ap.add_argument('--model')
    ap.add_argument('--out')
    ap.add_argument('--request-interval',type=float,default=15)
    ap.add_argument('--no-resume',action='store_true')
    a=ap.parse_args()
    if a.generator=='groq' and not a.model:ap.error('--generator groq requires --model')
    if a.model and a.generator!='groq':ap.error('--model requires --generator groq')
    out=Path(a.out) if a.out else ROOT/'results'/f'validation-comparison-{a.generator}'
    cases,corpus=ROOT/'data/validation/cases.jsonl',ROOT/'data/validation/corpus.jsonl'
    args=['--generator',a.generator,'--retriever','bm25,expanded_bm25','--judge','structured','--k','3','--cases',str(cases),'--corpus',str(corpus),'--out',str(out)]
    if a.generator=='groq':args+=['--model',a.model,'--request-interval',str(a.request_interval)]
    if a.no_resume:args+=['--no-resume']
    evaluate(args)
    reports=[json.loads((out/f'report_{name}_{a.generator}.json').read_text()) for name in ['bm25','expanded_bm25']]
    fields=['generator','model','k','support_judge','scoring_version','min_coverage']
    assert all(reports[0]['config'].get(f)==reports[1]['config'].get(f) for f in fields)
    assert reports[0]['config']['inputs']==reports[1]['config']['inputs']
    manifest={'evaluation_mode':'controlled_comparison','generator':a.generator,'model':a.model,'dataset':'validation_v1','k':3,'judge':'StructuredSupportJudge','scoring_version':'3.0','inputs':reports[0]['config']['inputs'],
      'reports':[{'path':f'report_{r["config"]["retriever"]}_{a.generator}.json','sha256':hashlib.sha256((out/f'report_{r["config"]["retriever"]}_{a.generator}.json').read_bytes()).hexdigest(),'recall_at_3':r['retrieval']['recall@3']['mean'],'mrr':r['retrieval']['mrr']['mean'],'pass_rate':r['end_to_end']['pass_rate'],'passes':r['end_to_end']['diagnosis_counts']['PASS'],'n':r['end_to_end']['n']} for r in reports]}
    (out/'comparison.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':main()
