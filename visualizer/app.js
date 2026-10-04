'use strict';
const $ = id => document.getElementById(id);
const state = {runs:[], validation:null, current:null, selected:null, imported:[], stage:'e2e', audited:false};
const labels = {PASS:'Pass',RETRIEVAL_MISS:'Retrieval miss',DISTRACTOR_INTERFERENCE:'Distractor interference',WRONG_ANSWER_GIVEN_GOLD:'Wrong answer',OVER_ABSTENTION:'Over-abstention',UNSUPPORTED_GENERATION:'Unsupported generation',ADVERSARIAL_COMPLIANCE:'Adversarial compliance',CITATION_UNFAITHFUL:'Citation support failure',ANSWER_FAILURE:'Answer failure'};
const pct = x => typeof x === 'number' && Number.isFinite(x) ? `${(100*x).toFixed(1)}%` : 'n/a';
const dec = x => typeof x === 'number' && Number.isFinite(x) ? x.toFixed(3) : 'n/a';
function el(tag, text, className) { const n = document.createElement(tag); if(text!==undefined)n.textContent=String(text); if(className)n.className=className; return n; }
function clear(id) { const n=typeof id==='string'?$(id):id;n.replaceChildren();return n; }
function showNotice(message) { $('notice').hidden=!message;$('notice').textContent=message; }
function config(run=state.current) {return run?.report.config || {};}
function dataset(run) {
 const p=config(run).inputs?.cases?.path || '';
 if(p.includes('/validation/'))return 'Fresh validation';
 if(p.includes('holdout'))return 'Audited holdout';
 if(p)return 'Development';
 return 'Unspecified dataset';
}
function runTitle(run) {const c=config(run);return `${c.retriever} · ${c.generator}`;}
function reviewed(row) {return state.current?.audit?.cases?.find(c=>c.id===row.id);}
function auditActive() {return state.audited && state.stage==='e2e' && !!state.current?.audit;}
function outcome(row) {
 if(auditActive())return reviewed(row)?.reviewed_diagnosis || row.diagnosis;
 if(state.stage==='e2e')return row.diagnosis;
 const s=row.oracle;
 return s.answer_ok ? (s.citation_ok===false?'CITATION_UNFAITHFUL':'PASS') : 'ANSWER_FAILURE';
}
function currentRows() {return state.current?.report.cases || [];}
function filteredRows() {
 const q=$('query').value.toLowerCase(), t=$('type').value, d=$('diagnosis').value;
 return currentRows().filter(c=>(!t||c.type===t)&&(!d||outcome(c)===d)&&(!$('failures').checked||outcome(c)!=='PASS')&&(!q||`${c.id} ${c.question} ${c[state.stage+'_answer']}`.toLowerCase().includes(q)));
}
function renderRuns() {
 const nav=clear('runs'), q=$('run-search').value.toLowerCase();
 const groups=new Map();
 for(const run of state.runs){if(q&&!`${runTitle(run)} ${config(run).model||''} ${run.path} ${dataset(run)}`.toLowerCase().includes(q))continue;const group=dataset(run);if(!groups.has(group))groups.set(group,[]);groups.get(group).push(run);}
 if(!groups.size){nav.append(el('p','No matching runs.','empty'));return;}
 for(const [name,runs] of groups){nav.append(el('div',name,'run-group'));for(const run of runs){const c=config(run);const button=el('button',undefined,'run-button'+(run.id===state.current?.id?' active':''));button.type='button';button.setAttribute('aria-current',run.id===state.current?.id?'true':'false');const title=el('span',undefined,'run-name');title.append(el('span',c.retriever),el('span',pct(run.report.end_to_end.pass_rate),'run-score'));button.append(title,el('small',c.model||`${c.generator} generator`),el('small',`${c.scoring_version||'1.0'} · ${run.report.cases.length} cases · ${c.evaluation_mode==='rescore_saved_answers'?'regraded':'generated'}`));button.onclick=()=>selectRun(run.id);nav.append(button);}}
}
function selectRun(id) {
 state.current=state.runs.find(r=>r.id===id);$('export').disabled=false;state.selected=null;state.audited=false;state.stage='e2e';$('stage').value='e2e';$('audited').checked=false;$('query').value='';$('type').value='';$('failures').checked=false;
 renderRuns();renderOverview();renderComparisonOptions();renderCases();
}
function bar(value) {const track=el('div',undefined,'track');const fill=el('div',undefined,'fill');fill.style.width=`${typeof value==='number'?Math.max(0,Math.min(1,value))*100:0}%`;track.append(fill);return track;}
function renderOverview() {
 if(!state.current)return;
 const r=state.current.report,c=r.config,rows=currentRows(),oracle=state.stage==='oracle';
 $('dataset-label').textContent=dataset(state.current);$('title').textContent=`${c.retriever.replaceAll('_',' ')} / ${c.generator}`;
 $('subtitle').textContent=`${c.model||'Deterministic extractive generation'} · ${rows.length} cases · ${r.retrieval.n} with gold evidence`;
 $('run-mode').textContent=auditActive()?'Assistant source audit':c.evaluation_mode==='rescore_saved_answers'?'Regraded saved answers':'Generated answers';
 $('audit-control').hidden=!state.current.audit||oracle;
 const prov=clear('provenance');for(const tag of [`K = ${c.k}`,c.support_judge||'Unknown judge',`Scoring ${c.scoring_version||'1.0'}`,state.current.path])prov.append(el('span',tag));
 const pass=rows.filter(x=>outcome(x)==='PASS').length;
 $('score-label').textContent=auditActive()?'Assistant-reviewed end-to-end pass rate':oracle?'Oracle answer + citation pass rate':'Automated end-to-end pass rate';
 clear('score').append(el('span',`${(100*pass/rows.length).toFixed(1)}`),el('small','%'));
 $('score-count').textContent=`${pass} / ${rows.length} cases pass`;
 const ci=r.end_to_end.pass_ci95;
 $('score-ci').textContent=auditActive()?'Separate assistant review; no independent adjudication':oracle?'Oracle evidence includes annotated hard negatives':Array.isArray(ci)?`95% bootstrap CI ${pct(ci[0])}–${pct(ci[1])}`:'Confidence interval unavailable';
 const stages=clear('stages');
 const attr=oracle?r.attribution_oracle:r.attribution_e2e;
 for(const [name,note,v] of [['Retrieval',`${r.retrieval.n} gold-evidence cases · recall@3`,r.retrieval['recall@3']?.mean],['Oracle answer',`${rows.length} cases · answer OK`,r.generation_oracle.answer_ok],['Source support',`${attr.n_answered} answered cases · citation OK`,attr.citation_ok_rate]]){
  const row=el('div',undefined,'stage-row');const title=el('div',name);title.append(el('small',note));row.append(title,bar(v),el('span',pct(v),'stage-value'));stages.append(row);
 }
 $('pipeline-context').textContent=auditActive()?'Original automated stage metrics':'Different denominators';
 const counts={};for(const row of rows){const d=outcome(row);counts[d]=(counts[d]||0)+1;}
 const diagnoses=clear('diagnoses');for(const [d,n] of Object.entries(counts).sort((a,b)=>b[1]-a[1])){
  const button=el('button',undefined,`diagnosis-row ${d==='PASS'?'pass':'fail'}`);button.append(el('span',labels[d]||d),bar(n/rows.length),el('span',n));button.onclick=()=>{$('diagnosis').value=d;renderCases();};diagnoses.append(button);
 }
 const filter=clear('diagnosis');filter.append(new Option('All outcomes',''));for(const d of Object.keys(counts))filter.append(new Option(labels[d]||d,d));
 renderValidation();
}
function metrics(run) {const r=run.report;return [['Recall@3',r.retrieval['recall@3']?.mean],['MRR',r.retrieval.mrr?.mean],['Oracle answer OK',r.generation_oracle.answer_ok],['Citation OK',r.attribution_e2e.citation_ok_rate],['End-to-end pass',r.end_to_end.pass_rate]];}
function comparability(a,b) {
 const x=a.report.config,y=b.report.config,issues=[];
 for(const [key,label] of [['generator','generator'],['model','model'],['k','K'],['support_judge','judge'],['scoring_version','scoring version'],['judge_model','judge model'],['min_coverage','abstention threshold'],['support_threshold','support threshold'],['max_tokens','token budget'],['reasoning_effort','reasoning setting']])if(x[key]!==y[key])issues.push(label);
 for(const [key,label] of [['cases','case set'],['corpus','corpus']]){
  const one=x.inputs?.[key]?.sha256,two=y.inputs?.[key]?.sha256;if(!one||!two||one!==two)issues.push(label);
 }
 if(JSON.stringify(a.report.cases.map(c=>c.id))!==JSON.stringify(b.report.cases.map(c=>c.id)))issues.push('evaluated cases/order');
 if(x.evaluation_mode==='rescore_saved_answers'||y.evaluation_mode==='rescore_saved_answers')issues.push('saved-answer replay');
 return issues;
}
function renderComparisonOptions() {const s=clear('compare');s.append(new Option('Choose a saved run',''));for(const r of state.runs)if(r.id!==state.current?.id)s.append(new Option(`${dataset(r)} / ${runTitle(r)} / ${config(r).scoring_version||'1.0'} / ${config(r).model||'extractive'}`,r.id));renderComparison();}
function renderComparison() {
 const body=clear('comparison-body'),other=state.runs.find(r=>r.id===$('compare').value);
 if(!other){body.textContent='Compare settings before interpreting a score difference.';return;}
 const issues=comparability(state.current,other);
 body.append(el('p',issues.length?`Descriptive comparison only. Differences or missing provenance: ${issues.join(', ')}.`:'Matched settings and input fingerprints. Both runs used the same cases, model, K and judge.',issues.length?'warning':'positive'));
 if(auditActive())body.append(el('p','This comparison uses automated report scores; the assistant audit is separate.','warning'));
 const table=el('table'),thead=el('thead'),tr=el('tr');for(const h of ['Metric','Selected','Compared','Δ'])tr.append(el('th',h));thead.append(tr);table.append(thead);const tbody=el('tbody');const one=metrics(state.current),two=metrics(other);
 for(let i=0;i<one.length;i++){const row=el('tr');const isMrr=one[i][0]==='MRR',format=isMrr?dec:pct;const delta=typeof one[i][1]==='number'&&typeof two[i][1]==='number'?(one[i][1]-two[i][1])*(isMrr?1:100):null;row.append(el('td',one[i][0]),el('td',format(one[i][1])),el('td',format(two[i][1])),el('td',delta===null?'n/a':`${delta>0?'+':''}${delta.toFixed(isMrr?3:1)}${isMrr?'':' pp'}`,delta>0?'positive':delta<0?'negative':''));tbody.append(row);}table.append(tbody);body.append(table,el('p','Selected minus compared. Different retrieval runs can also change model answers; one run is not a causal estimate.','muted'));
}
function renderValidation() {
 $('validation-panel').hidden=!state.validation; if(!state.validation)return;
 const body=clear('validation-body');body.append(el('p','Validation-v1: a separate fictional corpus and fixed assistant-authored labels. Support and refusal probes measure grading, not RAG performance. No general semantic-accuracy claim.'));
 const table=el('table'),head=el('tr');for(const t of ['Judge','Support','False accepts','False rejects','Refusal'])head.append(el('th',t));table.append(head);
 for(const [name,v] of Object.entries(state.validation.judges)){const tr=el('tr');for(const val of [name,`${v.support.tp+v.support.tn}/${v.support.n}`,v.support.fp,v.support.fn,`${pct(v.refusal.accuracy)} (${v.refusal.n})`])tr.append(el('td',val));table.append(tr);}body.append(table);
 const misses=el('details');misses.append(el('summary','Inspect disagreements'));for(const [name,v] of Object.entries(state.validation.judges))for(const row of v.support.cases.filter(x=>x.predicted!==x.expected)){const p=el('p',`${name} / ${row.id}: ${row.claim} Expected ${row.expected}; predicted ${row.predicted}.`);misses.append(p);}body.append(misses);
}
function renderCases() {
 if(!state.current)return;
 const rows=filteredRows(),list=clear('case-list');$('case-count').textContent=`${rows.length} / ${currentRows().length}`;
 if(!rows.length){list.append(el('p','No cases match these filters.','empty'));state.selected=null;clear('detail').append(el('p','Clear a filter to inspect cases.','muted'));return;}
 if(!rows.some(c=>c.id===state.selected))state.selected=rows[0].id;
 for(const c of rows){const button=el('button',undefined,`case-button${c.id===state.selected?' active':''}`);button.type='button';button.setAttribute('aria-pressed',String(c.id===state.selected));const meta=el('span',undefined,'case-meta');meta.append(el('span',`${c.id} · ${c.type}`),el('span',labels[outcome(c)]||outcome(c),`badge ${outcome(c)==='PASS'?'pass':'fail'}`));button.append(meta,el('span',c.question,'case-question'));button.onclick=()=>{state.selected=c.id;renderCases();};list.append(button);}renderDetail(rows.find(c=>c.id===state.selected));
}
function renderDetail(c) {
 const body=clear('detail'),score=c[state.stage],stage=state.stage;
 body.append(el('span',`${c.id} / ${labels[outcome(c)]||outcome(c)}`,`badge ${outcome(c)==='PASS'?'pass':'fail'}`),el('p',c.question,'question'),el('h3',stage==='oracle'?'Oracle answer':'Generated answer'),el('div',c[stage+'_answer'],'answer'));
 const chips=el('div',undefined,'metric-chips');for(const [label,val] of [['Answer OK',score.answer_ok],['Faithfulness',score.faithfulness===null?'n/a':dec(score.faithfulness)],['Citations valid',score.citations_valid],['Forbidden phrase',score.forbidden_phrase]])chips.append(el('span',`${label}: ${val===null?'n/a':val}`));body.append(chips);
 if(auditActive()){const rev=reviewed(c);if(rev)body.append(el('div',`Assistant review: ${rev.rationale} Original automated label: ${labels[c.diagnosis]||c.diagnosis}. Stage metrics above remain automated.`, 'review-note'));}
 body.append(el('h3',stage==='oracle'?'Oracle context order':'Retrieved context order'));
 const ids=stage==='oracle'?c.oracle_context:c.retrieved,cites=c[stage+'_citations'];const trace=el('div',undefined,'trace');
 for(const [i,id] of ids.entries()){const n=el('span',`${i+1}. ${id}${cites.includes(id)?' · cited':''}`,`${c.gold_ids.includes(id)?'gold ':''}${cites.includes(id)?'cited':''}`);trace.append(n);}if(!ids.length)trace.append(el('span','No context'));body.append(trace,el('p','Green marks gold evidence. Bold marks a cited source.','muted small'));
 body.append(el('h3','Source evidence'),el('p',state.current.evidence_status,'muted small'));
 const sourceIds=[...new Set([...cites,...ids])];for(const id of sourceIds){const doc=state.current.evidence[id],source=el('details',undefined,'source');source.open=cites.includes(id);const summary=el('summary');summary.append(el('strong',doc?.title||id),el('span',`${id}${cites.includes(id)?' · cited':''}`));source.append(summary,el('p',doc?.text||'Source text unavailable. Importing a report does not reconstruct its original corpus.'));body.append(source);}
 const meta=el('details',undefined,'source');meta.append(el('summary','Run provenance'),el('p',JSON.stringify(state.current.report.config,null,2),'answer'));body.append(meta);
}
function validReport(r) {return r&&r.config&&Array.isArray(r.cases)&&r.cases.length>0&&r.end_to_end&&r.retrieval&&r.generation_oracle&&r.attribution_e2e&&r.attribution_oracle&&r.cases.every(c=>typeof c.id==='string'&&typeof c.question==='string'&&typeof c.e2e_answer==='string'&&typeof c.oracle_answer==='string'&&Array.isArray(c.retrieved)&&Array.isArray(c.gold_ids)&&Array.isArray(c.oracle_context)&&Array.isArray(c.e2e_citations)&&Array.isArray(c.oracle_citations)&&c.e2e&&c.oracle);}
async function load() {
 const prior=state.current?.id;
 $('refresh').disabled=true;
 try{const response=await fetch('/api/data');if(!response.ok)throw Error(`HTTP ${response.status}`);const data=await response.json();state.runs=[...data.reports.filter(r=>validReport(r.report)),...state.imported];state.validation=data.validation;showNotice((data.warnings||[]).join(' '));
  if(state.runs.length)selectRun(state.runs.some(r=>r.id===prior)?prior:state.runs.find(r=>r.path.includes('groq-holdout-structured'))?.id||state.runs[0].id);
  else{state.current=null;renderRuns();showNotice('No saved reports found. Run an evaluation or import a report JSON.');$('export').disabled=true;}
 }catch(e){showNotice(`Could not load reports: ${e.message}. You can still import a report JSON.`);}finally{$('refresh').disabled=false;}
}
function exportCases() {
 const rows=filteredRows();const quote=x=>'"'+String(x??'').replaceAll('"','""')+'"';
 const lines=[['id','type','question','answer','citations','diagnosis','score_basis','stage'],...rows.map(c=>[c.id,c.type,c.question,c[state.stage+'_answer'],c[state.stage+'_citations'].join(';'),outcome(c),auditActive()?'assistant_audit':'automated',state.stage])];
 const url=URL.createObjectURL(new Blob(['\ufeff'+lines.map(row=>row.map(x=>quote(/^[=+@\-]/.test(String(x))?'\''+x:x)).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=el('a');a.href=url;a.download='rag-evaluation-cases.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$('refresh').onclick=load;$('run-search').oninput=renderRuns;$('query').oninput=renderCases;for(const id of ['type','diagnosis','failures'])$(id).onchange=renderCases;
$('reset-diagnosis').onclick=()=>{$('diagnosis').value='';renderCases();};$('compare').onchange=renderComparison;$('export').onclick=exportCases;
$('stage').onchange=()=>{state.stage=$('stage').value;renderOverview();renderComparison();renderCases();};$('audited').onchange=()=>{state.audited=$('audited').checked;renderOverview();renderComparison();renderCases();};
$('import').onchange=async()=>{const errors=[];let last=null;for(const file of $('import').files){try{if(file.size>20*1024*1024)throw Error('file exceeds 20 MB');const r=JSON.parse(await file.text());if(!validReport(r))throw Error('not a supported evaluation report');last={id:`import:${crypto.randomUUID()}`,path:file.name,report:r,evidence:{},evidence_status:'Imported report: source corpus unavailable.',audit:null};state.imported.push(last);state.runs.push(last);}catch(e){errors.push(`${file.name}: ${e.message}`);}}if(last){$('export').disabled=false;$('run-search').value='';selectRun(last.id);}showNotice(errors.join(' '));$('import').value='';};
load();
