"""Measure judge accuracy on fixed labeled probes, independently of generation."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rag_eval.attribution import ConservativeSupportJudge
from rag_eval.semantic import StructuredSupportJudge
from rag_eval.scoring import substantive_text, is_safe_refusal

ROOT = Path(__file__).resolve().parent.parent

def validate(directory):
    directory = Path(directory)
    support = [json.loads(line) for line in (directory / 'support_cases.jsonl').read_text().splitlines()]
    refusals = [json.loads(line) for line in (directory / 'refusal_cases.jsonl').read_text().splitlines()]
    results = {}
    for name, judge in [('conservative', ConservativeSupportJudge()), ('structured', StructuredSupportJudge())]:
        rows = []
        for c in support:
            rows.append({**c, 'predicted': judge.supported(c['claim'], c['evidence'])})
        check = getattr(judge, 'safe_refusal', is_safe_refusal)
        refusal_rows = [{**c, 'predicted_safe': not bool(substantive_text(c['text'], check).strip())} for c in refusals]
        tp = sum(c['expected'] and c['predicted'] for c in rows)
        fp = sum(not c['expected'] and c['predicted'] for c in rows)
        fn = sum(c['expected'] and not c['predicted'] for c in rows)
        tn = sum(not c['expected'] and not c['predicted'] for c in rows)
        results[name] = {'support': {'n': len(rows), 'accuracy': (tp+tn)/len(rows), 'tp':tp,'fp':fp,'fn':fn,'tn':tn,
            'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'cases':rows},
            'refusal': {'n':len(refusal_rows),'accuracy':sum(c['expected_safe']==c['predicted_safe'] for c in refusal_rows)/len(refusal_rows),'cases':refusal_rows}}
    return {'evaluation_mode':'judge_validation','dataset':'validation_v1','inputs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [directory/'support_cases.jsonl',directory/'refusal_cases.jsonl']},'judges':results,
            'limitations':['Small, assistant-authored synthetic probes; not independent expert annotation.','Created before implementing the structured judge; no tuning after observing this validation run.','Finite rules do not provide general semantic entailment.']}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',default=ROOT/'data/validation')
    ap.add_argument('--out',default=ROOT/'results/judge-validation')
    a=ap.parse_args(); r=validate(a.data); out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    (out/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
    lines=['# Fixed judge validation','', '| Judge | Support accuracy | False acceptances | False rejections | Refusal accuracy |','|---|---:|---:|---:|---:|']
    for name,v in r['judges'].items():
        s=v['support']; f=v['refusal'];line=f"| {name} | {s['accuracy']:.1%} ({s['tp']+s['tn']}/{s['n']}) | {s['fp']} | {s['fn']} | {f['accuracy']:.1%} |";lines.append(line);print(line)
        for c in s['cases']:
            if c['predicted']!=c['expected']:print(f"  mismatch: {c['id']} expected={c['expected']} predicted={c['predicted']}")
    lines+=['','These are synthetic source-support and refusal probes, not RAG pass rates.','No provider was called. Source hashes and every decision are in validation.json.','No independent expert annotations or general semantic-accuracy claims.']
    (out/'validation.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
