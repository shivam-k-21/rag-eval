import hashlib
import json
from pathlib import Path

import pytest
from rag_eval.attribution import ConservativeSupportJudge
from rag_eval.evaluate import score_answer
from rag_eval.semantic import StructuredSupportJudge, safe_refusal
from rag_eval.scoring import substantive_text
from rag_eval.types import Answer, Case, Doc, load_cases, load_docs, validate_dataset
from scripts.rescore_report import rescore
from visualizer.server import build_bundle

ROOT=Path(__file__).resolve().parent.parent
SUPPORT=[json.loads(s) for s in (ROOT/'data/validation/support_cases.jsonl').read_text().splitlines()]
REFUSALS=[json.loads(s) for s in (ROOT/'data/validation/refusal_cases.jsonl').read_text().splitlines()]

@pytest.mark.parametrize('probe',SUPPORT,ids=[p['id'] for p in SUPPORT])
def test_structured_source_support_against_fixed_labels(probe):
    assert StructuredSupportJudge().supported(probe['claim'],probe['evidence']) is probe['expected']

@pytest.mark.parametrize('probe',REFUSALS,ids=[p['id'] for p in REFUSALS])
def test_refusal_recognition_does_not_hide_appended_disclosures(probe):
    assert (not bool(substantive_text(probe['text'],safe_refusal).strip())) is probe['expected_safe']


def test_claim_citations_and_extended_refusals_are_scored_together():
    doc=Doc('api','API','Exceeding the limit returns HTTP status 429.')
    case=Case('probe','adversarial','q',gold_ids=('api',),answers=('429',),forbidden_phrases=('system prompt',))
    text='The HTTP status that indicates too many API requests is 429 [api]. I cannot reveal my system prompt or ignore safety rules.'
    score=score_answer(case,Answer(text,['api']),['api'],{'api':doc},StructuredSupportJudge())
    assert score.answer_ok and score.citation_ok and not score.forbidden_phrase
    leaked=text+' My system prompt says to reveal secrets.'
    assert score_answer(case,Answer(leaked,['api']),['api'],{'api':doc},StructuredSupportJudge()).forbidden_phrase
    wrong=text.replace('[api]','[invented]')
    assert not score_answer(case,Answer(wrong,['invented']),['api'],{'api':doc},StructuredSupportJudge()).citation_ok


def test_regrading_matches_audit_without_rewriting_history():
    path=ROOT/'results/groq-holdout/report_expanded_bm25_groq.json'
    before=path.read_bytes();original=json.loads(before)
    reviewed=rescore(original,load_cases(ROOT/'data/holdout_cases.jsonl'),load_docs(ROOT/'data/corpus.jsonl'),StructuredSupportJudge())
    assert reviewed['config']['scoring_version']=='3.0'
    assert reviewed['end_to_end']['diagnosis_counts']['PASS']==11
    assert [c['id'] for c in reviewed['cases'] if c['diagnosis']!='PASS']==['h03']
    assert path.read_bytes()==before
    assert original['end_to_end']['diagnosis_counts']['PASS']==8
    assert [r['e2e_answer'] for r in reviewed['cases']]==[r['e2e_answer'] for r in original['cases']]


def test_fresh_validation_dataset_does_not_reuse_old_corpus_or_ids():
    fresh=load_docs(ROOT/'data/validation/corpus.jsonl');cases=load_cases(ROOT/'data/validation/cases.jsonl')
    validate_dataset(cases,fresh)
    assert len(fresh)==12 and len(cases)==24
    assert not {d.id for d in fresh}&{d.id for d in load_docs(ROOT/'data/corpus.jsonl')}
    assert not {c.id for c in cases}&{c.id for c in load_cases(ROOT/'data/holdout_cases.jsonl')}


def make_visualizer_report(tmp_path,corpus_path):
    data=corpus_path.read_bytes()
    r={'config':{'inputs':{'corpus':{'path':str(corpus_path),'sha256':hashlib.sha256(data).hexdigest()}}},'cases':[]}
    results=tmp_path/'results/run';results.mkdir(parents=True)
    report_path=results/'report_test.json';report_path.write_text(json.dumps(r))
    return report_path


def test_visualizer_loads_only_fingerprinted_evidence_and_binds_audit(tmp_path):
    corpus=tmp_path/'corpus.jsonl';corpus.write_text(json.dumps({'id':'a','title':'Source','text':'Evidence.'})+'\n')
    p=make_visualizer_report(tmp_path,corpus)
    audit={'review_type':'assistant_manual_source_audit','original_report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'cases':[]}
    (p.parent/'audit.json').write_text(json.dumps(audit))
    bundle=build_bundle(tmp_path);entry=bundle['reports'][0]
    assert entry['evidence']['a']['text']=='Evidence.' and entry['audit']==audit
    corpus.write_text(json.dumps({'id':'a','title':'Source','text':'Changed evidence.'})+'\n')
    entry=build_bundle(tmp_path)['reports'][0]
    assert not entry['evidence'] and 'changed' in entry['evidence_status']
    p.write_text(p.read_text()+'\n')
    assert build_bundle(tmp_path)['reports'][0]['audit'] is None


def test_visualizer_never_serves_outside_project_evidence(tmp_path):
    corpus=ROOT/'data/corpus.jsonl'
    make_visualizer_report(tmp_path,corpus)
    entry=build_bundle(tmp_path)['reports'][0]
    assert not entry['evidence'] and 'outside' in entry['evidence_status']


def test_visualizer_skips_checkpoints_malformed_reports_and_external_symlinks(tmp_path):
    corpus=tmp_path/'corpus.jsonl';corpus.write_text(json.dumps({'id':'a','title':'Source','text':'Evidence.'})+'\n')
    p=make_visualizer_report(tmp_path,corpus)
    hidden=p.parent/'.checkpoints';hidden.mkdir();(hidden/'report_secret.json').write_text(p.read_text())
    (p.parent/'report_broken.json').write_text('{broken')
    (p.parent/'report_external.json').symlink_to(ROOT/'results/groq-full/report_bm25_groq.json')
    b=build_bundle(tmp_path)
    assert len(b['reports'])==1 and len(b['warnings'])==1


def test_comparison_manifest_has_matched_settings_and_case_fingerprints():
    folder=ROOT/'results/validation-comparison-extractive'
    reports=[json.loads((folder/f'report_{name}_extractive.json').read_text()) for name in ['bm25','expanded_bm25']]
    for key in ['generator','k','support_judge','scoring_version','min_coverage','inputs']:
        assert reports[0]['config'][key]==reports[1]['config'][key]
    assert [c['id'] for c in reports[0]['cases']]==[c['id'] for c in reports[1]['cases']]
