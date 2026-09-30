"""Resumable weekly pipeline. Dry-run by default; explicit publish + Pages + Notion gates."""
import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from weekly_common import (DATA_SOURCE, VERSION, frozen, lesson_id, notion_plan, protected,
                           read, require, safe_fragments, schema_check, sha, text_sha, unchanged, write)
from generate_new_japanese_content import author

ROOT = Path(__file__).resolve().parents[1]

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8')

def now():
    return datetime.now(timezone.utc).isoformat()

def command(args, cwd=ROOT, env=None):
    p = subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
    require(p.returncode == 0, f'Command failed ({p.returncode}): {args[0]}\n{p.stdout}\n{p.stderr}')
    return p.stdout.strip()

def git(*args):
    return command(['git',*args])

def inventory(root):
    """Published = tracked HEAD HTML with date ID and matching displayed date, not draft JSON."""
    names = command(['git','ls-tree','-r','--name-only','HEAD','--','japanese'],root).splitlines()
    found=[]
    for name in names:
        match = re.fullmatch(r'japanese/(JP-V1-(\d{4})-W(\d{2})-D([1-7]))\.html',name)
        if not match:
            continue
        day = date.fromisocalendar(*map(int,match.groups()[1:]))
        text = command(['git','show','HEAD:'+name],root)
        require(f'Lesson ID：{match[1]}' in text and f'class="tag">{day.isoformat()}</span>' in text,
                'Published date/ID mismatch: '+name)
        found.append({'id':match[1],'date':day.isoformat()})
    require(found,'No dated published lessons; manual baseline required')
    return sorted(found,key=lambda x:x['date'])

def make_plan(existing, today, target=None):
    latest = max(existing,key=lambda x:x['date'])
    if target:
        require(re.fullmatch(r'\d{4}-W\d{2}',target),'Invalid target week')
        y,w=map(int,target.replace('-W','-').split('-'))
        start=date.fromisocalendar(y,w,1)
        require(start >= today-timedelta(days=today.weekday()),'Historical backfill forbidden')
    else:
        anchor=max(today,date.fromisoformat(latest['date']))
        start=anchor+timedelta(days=7-anchor.weekday())
    week=f'{start.isocalendar().year}-W{start.isocalendar().week:02d}'
    by_id={x['id']:x['date'] for x in existing}
    days=[start+timedelta(days=i) for i in range(7)]
    missing=[{'id':lesson_id(d),'date':d.isoformat()} for d in days if lesson_id(d) not in by_id]
    return {'week':week,'asOf':today.isoformat(),'latest':latest,'weekStart':start.isoformat(),
            'missing':missing,'existing':[x for x in existing if x['id'].startswith('JP-V1-'+week+'-')]}

def valid_context(context, today):
    require(context.get('status') == 'checked', 'Feedback lookup unavailable; do not assume no feedback')
    checked=date.fromisoformat(context['checkedAt'][:10])
    require(0 <= (today-checked).days <= 7,'Context is stale; Work must refresh Notion/research')
    require(context.get('dataSource') == DATA_SOURCE and context.get('complete') is True,'Incomplete feedback query')
    require(isinstance(context.get('feedback'),list),'Missing feedback list')
    if not context['feedback']:
        require(context.get('sources'), 'No valid feedback; researched source context required')
    for source in context.get('sources',[]):
        require(source.get('url','').startswith('https://') and source.get('summary'),'Invalid research source')

def prepare(args):
    frozen(ROOT)
    today=date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone(timedelta(hours=8))).date()
    active=ROOT/'.weekly/active.json'
    if active.exists() and not args.target_week:
        current=read(active)
        require(re.fullmatch(r'\d{4}-W\d{2}',current['week']),'Invalid active week state')
        run=ROOT/'.weekly'/current['week']
        state=read(run/'state.json')
        if state['status'] != 'complete':
            plan=read(run/'plan.json')
            require(date.fromisoformat(plan['weekStart']) >= today-timedelta(days=today.weekday()),
                    'Pending run expired; explicitly select a current/future --target-week after review')
            return run
    require(args.context,'First run needs fresh Work context: --context path.json')
    context=read(args.context)
    valid_context(context,today)
    plan=make_plan(inventory(ROOT),today,args.target_week)
    run=ROOT/'.weekly'/plan['week']
    if (run/'plan.json').exists():
        return run  # pinned batch; do not jump forward on Monday or after push
    require(plan['missing'],'Week already complete; no new content needed')
    write(run/'plan.json',plan)
    write(run/'context.json',context)
    write(run/'baseline.json',protected(ROOT))
    write(run/'state.json',{'status':'prepared','baseCommit':git('rev-parse','HEAD'),'createdAt':now()})
    write(active,{'week':plan['week']})
    return run

def validate_content(root, plan, data, context):
    require(not set(data)-{'templateVersion','week','partialWeek','contentPolicy','lessons'},'Unexpected content envelope fields')
    require(data.get('templateVersion') == VERSION and data.get('week') == plan['week'],'Envelope version/week mismatch')
    require(data.get('partialWeek',False) is (len(plan['missing']) < 7),'partialWeek mismatch')
    lessons=data.get('lessons',[])
    require([{'id':x['lesson']['id'],'date':x['lesson']['date']} for x in lessons] == plan['missing'],
            'Content does not exactly match missing dates/IDs')
    schema=read(root/'generator/template-schema.json')
    readings=[]
    for item in lessons:
        schema_check(item,schema)
        safe_fragments(item)
        meta=item['lesson']
        require(meta['id']==lesson_id(date.fromisoformat(meta['date'])),'ISO ID mismatch')
        require(not (root/'japanese'/f'{meta["id"]}.html').exists(),'Existing lesson refuses overwrite')
        require(len(item['usefulSentences']) == 10,'Need 10 useful sentences')
        require(len({x['japaneseHtml'] for x in item['usefulSentences']})==10,'Duplicate useful sentences')
        require([q['id'] for q in item['quiz']]==['q1','q2','q3','q4'],'Quiz IDs must match frozen feedback UI')
        require([q['type'] for q in item['quiz']]==['singleChoice','text','textarea','textarea'],'Quiz types mismatch')
        choices=item['quiz'][0].get('choices',[])
        require(len(choices)>=2 and len({x['value'] for x in choices})==len(choices),'Invalid choice IDs')
        reading=re.sub('<[^>]+>','',re.sub(r'<rt>.*?</rt>','',item['reading']['japaneseHtml']))
        require(len(reading)>=100,'Reading too short')
        readings.append(reading)
        require(len(item['patterns'])>=2 and len(item['vocabulary'])>=4,'Insufficient teaching content')
    require(len(set(readings))==len(readings),'Repeated readings')
    domains=[x['lesson']['domain'] for x in lessons]
    require(len(set(domains))>=min(4,len(domains)),'Insufficient topic rotation')
    require(not any(domains[i]==domains[i+1]==domains[i+2] for i in range(len(domains)-2)),
            'Three consecutive lessons in same domain')
    for old in (root/'generator').glob('*content*.json'):
        if old.name.startswith('sample'):
            continue
        previous=read(old)
        for item in previous.get('lessons',[]):
            oldtext=re.sub('<[^>]+>','',re.sub(r'<rt>.*?</rt>','',item['reading']['japaneseHtml']))
            require(oldtext not in readings,'Copied existing reading')
    for feedback in context['feedback']:
        for target in feedback.get('targets',[]):
            teaching=json.dumps([{k:x[k] for k in ('patterns','quiz','outputPractice','previousReview')} for x in lessons],ensure_ascii=False)
            require(target in teaching,'Feedback target missing from teaching: '+target)
    return lessons

def stage(run, accept_revision=False):
    plan=read(run/'plan.json'); state=read(run/'state.json')
    require(state['status'] not in {'committed','pushed','pages_verified','complete'},'Published run cannot be restaged')
    unchanged(ROOT,read(run/'baseline.json'))
    index_before=sha(ROOT/'index.html')
    require(git('rev-parse','HEAD')==state['baseCommit'],'Repo HEAD changed; review and prepare a new run')
    data=read(run/'content.json')
    lessons=validate_content(ROOT,plan,data,read(run/'context.json'))
    # New isolated attempt; never remove/overwrite the previous preview on QA failure.
    preview=run/('stage-'+str(time.time_ns()))
    preview.mkdir()
    for folder in ('generator','templates','japanese'):
        shutil.copytree(ROOT/folder,preview/folder,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT/'index.html',preview/'index.html')
    content_name=f'generator/weekly-content-{plan["week"]}.json'
    require(not (ROOT/content_name).exists(),'Existing content JSON refuses overwrite')
    write(preview/content_name,data)
    output=command([sys.executable,str(preview/'generator/generate_weekly_japanese.py'),'--content',str(preview/content_name)],preview)
    (preview/'qa.log').write_text(output+'\n',encoding='utf-8')
    paths=[content_name,'index.html']+[f'japanese/{x["lesson"]["id"]}.html' for x in lessons]
    template=(ROOT/'templates/japanese-lesson-v1.html').read_text(encoding='utf-8')
    node=shutil.which('node')
    if not node:
        bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
        node=str(bundled) if bundled.is_file() else None
    require(node,'Node is required for JavaScript syntax QA')
    for rel in paths[2:]:
        text=(preview/rel).read_text(encoding='utf-8')
        require(re.findall(r'<style>(.*?)</style>',text,re.S)==re.findall(r'<style>(.*?)</style>',template,re.S),'Frozen CSS changed')
        require(text.count('<ruby>')==text.count('<rt>')==text.count('</ruby>'),'Ruby mismatch')
        scripts=re.findall(r'<script>(.*?)</script>',text,re.S)
        result=subprocess.run([node,'--check','-'],input='\n'.join(scripts),text=True,encoding='utf-8',capture_output=True)
        require(result.returncode==0,'JavaScript QA failed: '+result.stderr)
    unchanged(preview,read(run/'baseline.json'))
    unchanged(ROOT,read(run/'baseline.json'))
    require(sha(ROOT/'index.html')==index_before,'Formal index changed during dry run')
    regressions=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','generator','-p','test*.py','-v'],
                               cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=180)
    (preview/'qa.log').write_text(output+'\n'+regressions.stdout+'\n'+regressions.stderr,encoding='utf-8')
    require(regressions.returncode==0,'Regression QA failed; see staging qa.log; publication blocked')
    hashes={p:text_sha((preview/p).read_text(encoding='utf-8')) for p in paths}
    manifest={'week':plan['week'],'stage':str(preview),'files':hashes,'contentHash':sha(run/'content.json'),
              'qa':'passed','regressionTests':'passed','checkedAt':now(),'baseCommit':state['baseCommit']}
    if (run/'manifest.json').exists():
        previous=read(run/'manifest.json')
        if previous['files']!=hashes:
            require(accept_revision,'Retry content changed; explicit --accept-revision required')
            write(run/'manifest-history'/f'{previous["contentHash"]}.json',previous)
    write(run/'manifest.json',manifest)
    state['status']='staged'; write(run/'state.json',state)
    print('STAGED '+str(preview))

def checked_manifest(run):
    manifest=read(run/'manifest.json')
    plan=read(run/'plan.json')
    expected={'index.html',f'generator/weekly-content-{plan["week"]}.json',
              *[f'japanese/{x["id"]}.html' for x in plan['missing']]}
    require(set(manifest['files'])==expected,'Manifest publish allowlist mismatch')
    require(Path(manifest['stage']).resolve().is_relative_to(run.resolve()),'Stage path escapes run directory')
    require(manifest['qa']=='passed' and manifest.get('regressionTests')=='passed'
            and sha(run/'content.json')==manifest['contentHash'],'QA evidence stale')
    for name,digest in manifest['files'].items():
        require(text_sha((Path(manifest['stage'])/name).read_text(encoding='utf-8'))==digest,'Preview changed after QA')
    unchanged(Path(manifest['stage']),read(run/'baseline.json'))
    return manifest

def refresh_base(run):
    """Explicitly rebind an unpublished Candidate after committing tooling only."""
    state=read(run/'state.json')
    require(state['status'] in {'prepared','staged'} and not state.get('commit'), 'Published/committed run cannot refresh base')
    unchanged(ROOT,read(run/'baseline.json'))
    require(not git('diff','--name-only') and not git('diff','--cached','--name-only'), 'Commit/review tracked tooling changes first')
    for item in read(run/'plan.json')['missing']:
        require(not (ROOT/'japanese'/f'{item["id"]}.html').exists(), 'Target lesson already exists; do not rebind')
    old=state['baseCommit']; new=git('rev-parse','HEAD')
    require(not git('diff','--name-only',old,new,'--','index.html'), 'Formal index changed; explicit new planning required')
    write(run/'base-history'/f'{old}.json',state)
    state.update(status='prepared',baseCommit=new)
    write(run/'state.json',state)
    print('BASE_REFRESHED; stage and editorial review required')

def publish(run):
    """One exact allowlisted Git tree/commit. No broad git add, force push, or root file writes."""
    state=read(run/'state.json'); manifest=checked_manifest(run)
    today=datetime.now(timezone(timedelta(hours=8))).date()
    require(date.fromisoformat(read(run/'plan.json')['weekStart']) >= today-timedelta(days=today.weekday()),
            'Expired week cannot be published automatically')
    valid_context(read(run/'context.json'),today)
    unchanged(ROOT,read(run/'baseline.json'))
    require(not git('diff','--name-only') and not git('diff','--cached','--name-only'),'Tracked repo changes: commit/review tooling first')
    require(git('rev-parse','HEAD')==state['baseCommit'],'HEAD changed; preview must be rebuilt')
    remote=git('remote','get-url','origin')
    require(remote in {'https://github.com/noahel815/language-learning.git','https://github.com/noahel815/language-learning',
                        'git@github.com:noahel815/language-learning.git'},'Unexpected origin')
    if state['status']=='staged':
        review=read(run/'editorial-review.json')
        require(review.get('contentHash')==manifest['contentHash'] and review.get('approved') is True and review.get('reviewer'),
                'Content and mobile preview review required before publishing')
        require(review.get('mobilePreview') == 'passed' and review.get('answersChecked') is True,
                'Mobile preview and independent answer review required')
        env=os.environ.copy(); env['GIT_INDEX_FILE']=str(run/'publish.index')
        command(['git','read-tree',state['baseCommit']],env=env)
        for name in manifest['files']:
            blob=git('hash-object','-w','--',str(Path(manifest['stage'])/name))
            command(['git','update-index','--add','--cacheinfo','100644',blob,name],env=env)
        tree=command(['git','write-tree'],env=env)
        sha_commit=git('commit-tree',tree,'-p',state['baseCommit'],'-m','Publish Japanese '+manifest['week'])
        state.update(status='committed',commit=sha_commit); write(run/'state.json',state)
    require(state['status'] in {'committed','pushed','pages_verified','complete'},'Run not ready to publish')
    remote_sha=git('ls-remote','origin','refs/heads/main').split()[0]
    require(remote_sha in {state['baseCommit'],state['commit']},'Remote advanced; do not overwrite/rebase published lessons automatically')
    if remote_sha!=state['commit']:
        git('push','origin',state['commit']+':refs/heads/main')
    state['status']='pushed';write(run/'state.json',state)
    # Keep checkout untouched until operator/Work explicitly fast-forwards after completion.
    print('PUSHED '+state['commit'])

def http(url):
    req=urllib.request.Request(url,headers={'User-Agent':'language-learning-weekly','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=30) as response:
        return response.read()

def pages_success(runs, commit):
    candidates=[r for r in runs if r.get('head_sha')==commit and r.get('name','').lower()=='pages build and deployment']
    candidates.sort(key=lambda r:r.get('id',0),reverse=True)
    if not candidates:
        return None
    run=candidates[0]
    if run.get('status')!='completed':
        return None
    require(run.get('conclusion')=='success','Pages deployment failed: '+str(run.get('html_url')))
    return run

def verify_pages(run, timeout=900):
    state=read(run/'state.json'); manifest=checked_manifest(run)
    require(state['status'] in {'pushed','pages_verified','complete'},'Pages gate requires published commit')
    deadline=time.monotonic()+timeout
    while True:
        payload=json.loads(http('https://api.github.com/repos/noahel815/language-learning/actions/runs?head_sha='+state['commit']+'&per_page=100'))
        deployment=pages_success(payload.get('workflow_runs',[]),state['commit'])
        if deployment:
            matches=True
            for name,digest in manifest['files'].items():
                if name.startswith('generator/'):
                    continue
                remote=http('https://noahel815.github.io/language-learning/'+name+'?commit='+state['commit']).decode('utf-8')
                matches &= text_sha(remote)==digest
            if matches:
                write(run/'pages-receipt.json',{'commit':state['commit'],'run':deployment['html_url'],'checkedAt':now(),'files':manifest['files']})
                state['status']='pages_verified';write(run/'state.json',state)
                return
        require(time.monotonic()<deadline,'Pages verification timeout; Notion is blocked')
        print('WAITING_PAGES',flush=True);time.sleep(15)

def sync_plan(run, snapshot, dry=False, acquire=True):
    state=read(run/'state.json'); manifest=checked_manifest(run)
    if not dry:
        require(state['status'] in {'pages_verified','complete'},'Notion blocked until Pages success')
        require(read(run/'pages-receipt.json')['commit']==state['commit'],'Pages commit mismatch')
    evidence=read(snapshot)
    require(evidence.get('dataSource')==DATA_SOURCE and evidence.get('complete') is True,'Notion query must be complete')
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(evidence['checkedAt'])).total_seconds()
    require(0<=age<=3600,'Notion dedup snapshot must be refreshed within one hour')
    actions=notion_plan(read(run/'content.json')['lessons'],evidence['rows'])
    if not dry and acquire:
        lease=run/'notion-sync.lock'
        fd=os.open(lease,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        os.write(fd,now().encode());os.close(fd)
    write(run/('notion-dry-plan.json' if dry else 'notion-write-plan.json'),
          {'dryRun':dry,'commit':state.get('commit'),'contentHash':manifest['contentHash'],'actions':actions})
    return actions

def complete(run, readback):
    state=read(run/'state.json')
    require(state['status']=='pages_verified','Completion requires Pages verified')
    actions=sync_plan(run,readback,acquire=False)
    require(all(x['action']=='skip' for x in actions),'Notion readback missing lessons')
    unchanged(ROOT,read(run/'baseline.json'))
    head=git('rev-parse','HEAD')
    require(head in {state['baseCommit'],state['commit']},'Local HEAD advanced; reconcile explicitly')
    if head!=state['commit']:
        git('merge','--ff-only',state['commit'])
    state.update(status='complete',completedAt=now());write(run/'state.json',state)
    (run/'notion-sync.lock').unlink(missing_ok=True)

@contextlib.contextmanager
def lock():
    path=ROOT/'.weekly/pipeline.lock';path.parent.mkdir(exist_ok=True)
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    os.write(fd,str(os.getpid()).encode());os.close(fd)
    try:
        yield
    finally:
        path.unlink()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['dry-run','prepare','stage','refresh-base','publish','verify-pages','notion-plan','complete'])
    parser.add_argument('--context',type=Path)
    parser.add_argument('--run',type=Path)
    parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--as-of')
    parser.add_argument('--target-week')
    parser.add_argument('--backend',choices=['codex','work'],default='codex')
    parser.add_argument('--dry',action='store_true')
    parser.add_argument('--accept-revision',action='store_true',help='Archive previous manifest and QA a changed unpublished Candidate')
    args=parser.parse_args();run=None
    try:
        with lock():
            run=args.run.resolve() if args.run else None
            if run:
                require(run.is_relative_to(ROOT/'.weekly'),'Run path must stay inside repo .weekly')
            if args.action in {'prepare','dry-run'}:
                run=run or prepare(args)
                print('RUN '+str(run),flush=True)
                if read(run/'state.json')['status']=='complete':
                    print('ALREADY_COMPLETE: no new content or duplicate publication')
                    return 0
                if args.action=='dry-run':
                    if author(ROOT,run,args.backend) is None:
                        with (run/'events.jsonl').open('a',encoding='utf-8') as log:
                            log.write(json.dumps({'at':now(),'step':'author','result':'AUTHOR_REQUIRED','exitCode':20})+'\n')
                        return 20
                    stage(run)
            else:
                require(run and run.is_relative_to(ROOT/'.weekly'),'--run must be a repo .weekly directory')
                if args.action=='stage': stage(run,args.accept_revision)
                elif args.action=='refresh-base': refresh_base(run)
                elif args.action=='publish': publish(run)
                elif args.action=='verify-pages': verify_pages(run)
                elif args.action=='notion-plan': sync_plan(run,args.snapshot,args.dry)
                elif args.action=='complete': complete(run,args.snapshot)
            with (run/'events.jsonl').open('a',encoding='utf-8') as log:
                log.write(json.dumps({'at':now(),'step':args.action,'result':'success'})+'\n')
            return 0
    except Exception as e:
        message={'at':now(),'step':args.action,'result':'failed','error':str(e)}
        print(json.dumps(message,ensure_ascii=False),file=sys.stderr)
        if run and run.exists():
            with (run/'events.jsonl').open('a',encoding='utf-8') as log: log.write(json.dumps(message,ensure_ascii=False)+'\n')
        return 1

if __name__=='__main__':
    sys.exit(main())
