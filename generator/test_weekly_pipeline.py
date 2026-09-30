"""Safety regressions: all mutations occur in disposable directories; network mocked."""
import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
import weekly_orchestrator as pipeline
from weekly_common import DATA_SOURCE, frozen, notion_plan, read, schema_check, text_sha, write

ROOT=Path(__file__).resolve().parents[1]

class WeeklyTests(unittest.TestCase):
    def setUp(self):
        self.data=read(ROOT/'generator/fixtures/weekly-content-2026-W41-candidate.json')
        self.schema=read(ROOT/'generator/template-schema.json')
        self.existing=[{'id':'JP-V1-2026-W40-D3','date':'2026-09-30'}]
        self.plan=pipeline.make_plan(self.existing,date(2026,9,30))
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.run=Path(self.temp.name)
        self.validation_root=self.run/'validation'
        (self.validation_root/'generator').mkdir(parents=True)
        (self.validation_root/'japanese').mkdir()
        for name in ('template-schema.json','weekly-content-2026-W40-recovery.json'):
            shutil.copy2(ROOT/'generator'/name,self.validation_root/'generator'/name)

    def test_next_week(self):
        self.assertEqual(self.plan['week'],'2026-W41')
        self.assertEqual(self.plan['missing'][0],{'id':'JP-V1-2026-W41-D1','date':'2026-10-05'})
        self.assertEqual(self.plan['missing'][-1]['date'],'2026-10-11')

    def test_iso_year_boundary(self):
        p=pipeline.make_plan([{'id':'JP-V1-2026-W53-D4','date':'2026-12-31'}],date(2026,12,31))
        self.assertEqual(p['week'],'2027-W01')
        self.assertEqual(p['missing'][0]['date'],'2027-01-04')

    def test_sunday_and_monday_retry_same_target(self):
        sunday=pipeline.make_plan(self.existing,date(2026,10,4))
        monday=pipeline.make_plan(self.existing,date(2026,10,5),sunday['week'])
        self.assertEqual(sunday['missing'],monday['missing'])

    def test_partial_week_only_missing(self):
        p=pipeline.make_plan(self.existing+[{'id':'JP-V1-2026-W41-D1','date':'2026-10-05'}],date(2026,10,5),'2026-W41')
        self.assertEqual(len(p['missing']),6)
        self.assertEqual(p['missing'][0]['id'],'JP-V1-2026-W41-D2')

    def test_no_historical_backfill(self):
        with self.assertRaises(ValueError): pipeline.make_plan(self.existing,date(2026,9,30),'2026-W38')

    def test_schema_all_seven(self):
        for lesson in self.data['lessons']: schema_check(lesson,self.schema)

    def test_schema_rejects_extra_and_bad_type_and_pitch(self):
        for mutation in ('extra','max','pitch'):
            lesson=copy.deepcopy(self.data['lessons'][0])
            if mutation=='extra': lesson['reading']['unknown']=1
            elif mutation=='max': lesson['outputPractice']['maxLength']=True
            else: lesson['vocabulary'][0].update(pitchVerified=False,pitch='①')
            with self.assertRaises(ValueError): schema_check(lesson,self.schema)

    def test_content_exact_ids(self):
        pipeline.validate_content(self.validation_root,self.plan,self.data,{'feedback':[]})
        self.data['lessons'][1]['lesson']['id']=self.data['lessons'][0]['lesson']['id']
        with self.assertRaises(ValueError): pipeline.validate_content(self.validation_root,self.plan,self.data,{'feedback':[]})

    def test_content_date_week_mismatch(self):
        self.data['week']='2026-W40'
        with self.assertRaises(ValueError): pipeline.validate_content(self.validation_root,self.plan,self.data,{'feedback':[]})

    def test_existing_lesson_refused(self):
        with patch.object(Path,'exists',return_value=True):
            with self.assertRaisesRegex(ValueError,'overwrite'):
                pipeline.validate_content(self.validation_root,self.plan,self.data,{'feedback':[]})

    def test_injection_refused(self):
        self.data['lessons'][0]['reading']['japaneseHtml']='<p onclick="alert(1)">bad</p>'
        with self.assertRaisesRegex(ValueError,'Unsafe'):
            pipeline.validate_content(self.validation_root,self.plan,self.data,{'feedback':[]})

    def test_feedback_must_be_in_teaching(self):
        with self.assertRaisesRegex(ValueError,'Feedback target'):
            pipeline.validate_content(self.validation_root,self.plan,self.data,{'feedback':[{'targets':['架空未納入弱點']} ]})

    def test_frozen_current(self): frozen(ROOT)

    def test_lf_crlf_digest(self): self.assertEqual(text_sha('a\nb\n'),text_sha('a\r\nb\r\n'))

    def test_notion_create_skip_preserves_progress(self):
        actions=notion_plan(self.data['lessons'],[])
        rows=[{**a['properties'],'狀態':'完成','完成':'__YES__'} for a in actions]
        again=notion_plan(self.data['lessons'],rows)
        self.assertTrue(all(a['action']=='skip' for a in again))
        self.assertTrue(all(r['狀態']=='完成' for r in rows))

    def test_notion_duplicate_or_conflict_stops(self):
        row=notion_plan(self.data['lessons'],[])[0]['properties']
        with self.assertRaisesRegex(ValueError,'Duplicate'): notion_plan(self.data['lessons'],[row,row])
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            notion_plan(self.data['lessons'],[{**row,'教材網址':'https://wrong.example/'}])

    def test_pages_exact_commit_and_failure(self):
        base={'id':1,'name':'pages build and deployment','head_sha':'abc','status':'completed','conclusion':'success'}
        self.assertIsNone(pipeline.pages_success([base],'wrong'))
        self.assertEqual(pipeline.pages_success([base],'abc'),base)
        with self.assertRaisesRegex(ValueError,'failed'):
            pipeline.pages_success([{**base,'conclusion':'failure'}],'abc')

    def test_notion_before_pages_blocked(self):
        write(self.run/'state.json',{'status':'staged'})
        with patch.object(pipeline,'checked_manifest',return_value={}):
            with self.assertRaisesRegex(ValueError,'Pages'):
                pipeline.sync_plan(self.run,None)

    def test_completion_missing_readback_blocked(self):
        write(self.run/'state.json',{'status':'pages_verified'})
        with patch.object(pipeline,'sync_plan',return_value=[{'action':'create'}]):
            with self.assertRaisesRegex(ValueError,'missing'):
                pipeline.complete(self.run,None)

    def test_concurrent_run_blocked(self):
        with patch.object(pipeline,'ROOT',self.run):
            with pipeline.lock():
                with self.assertRaises(FileExistsError):
                    with pipeline.lock(): pass

    def test_context_unavailable_or_stale_not_empty(self):
        for context in ({'status':'unavailable'}, {'status':'checked','checkedAt':'2020-01-01'}):
            with self.assertRaises(ValueError): pipeline.valid_context(context,date(2026,9,30))

    def test_atomic_commit_and_push_retry(self):
        repo=self.run/'repo';repo.mkdir()
        real_command=pipeline.command
        def g(*args): return real_command(['git',*args],repo)
        g('init');g('config','user.email','test@example.invalid');g('config','user.name','Test')
        (repo/'keep.txt').write_text('existing',encoding='utf-8')
        g('add','keep.txt');g('commit','-m','baseline')
        base=g('rev-parse','HEAD')
        batch=repo/'.weekly/2026-W41';batch.mkdir(parents=True)
        stage=batch/'stage';stage.mkdir()
        (stage/'index.html').write_text('new',encoding='utf-8')
        write(batch/'state.json',{'status':'staged','baseCommit':base})
        write(batch/'baseline.json',{})
        write(batch/'plan.json',{'weekStart':(date.today()+timedelta(days=7)).isoformat()})
        write(batch/'context.json',{})
        write(batch/'editorial-review.json',{'contentHash':'h','approved':True,'reviewer':'test','mobilePreview':'passed','answersChecked':True})
        manifest={'stage':str(stage),'files':{'index.html':'hash'},'contentHash':'h','week':'2026-W41'}
        calls=[]
        def fake_git(*args):
            if args[:2]==('remote','get-url'): return 'https://github.com/noahel815/language-learning.git'
            if args[0]=='ls-remote': return base+'\trefs/heads/main'
            if args[0]=='push':
                calls.append(args)
                if len(calls)==1: raise ValueError('simulated push failure')
                return ''
            return g(*args)
        real_command=pipeline.command
        with patch.object(pipeline,'ROOT',repo),patch.object(pipeline,'git',side_effect=fake_git), \
             patch.object(pipeline,'command',side_effect=lambda args,env=None:real_command(args,repo,env)), \
             patch.object(pipeline,'checked_manifest',return_value=manifest),patch.object(pipeline,'unchanged'), \
             patch.object(pipeline,'valid_context'),patch('sys.stdout'):
            with self.assertRaisesRegex(ValueError,'push failure'): pipeline.publish(batch)
            commit=read(batch/'state.json')['commit']
            self.assertEqual(read(batch/'state.json')['status'],'committed')
            pipeline.publish(batch)
            self.assertEqual(read(batch/'state.json')['commit'],commit)
            self.assertEqual(g('diff-tree','--no-commit-id','--name-only','-r',commit),'index.html')
            self.assertEqual(g('rev-parse','HEAD'),base)
            self.assertEqual((repo/'keep.txt').read_text(),'existing')

    def test_refresh_base_only_before_publication(self):
        write(self.run/'state.json',{'status':'staged','baseCommit':'old'})
        write(self.run/'baseline.json',{})
        write(self.run/'plan.json',{'missing':[{'id':'JP-V1-2026-W41-D1'}]})
        with patch.object(pipeline,'ROOT',self.run),patch.object(pipeline,'unchanged'), \
             patch.object(pipeline,'git',side_effect=lambda *args: 'new' if args[0]=='rev-parse' else ''),patch('sys.stdout'):
            pipeline.refresh_base(self.run)
            self.assertEqual(read(self.run/'state.json')['baseCommit'],'new')
            self.assertEqual(read(self.run/'state.json')['status'],'prepared')
            write(self.run/'state.json',{'status':'pushed','baseCommit':'old','commit':'published'})
            with self.assertRaises(ValueError): pipeline.refresh_base(self.run)

    def test_failed_pages_never_writes_receipt(self):
        write(self.run/'state.json',{'status':'pushed','commit':'abc'})
        payload=json.dumps({'workflow_runs':[{'id':1,'head_sha':'abc','name':'pages build and deployment',
                         'status':'completed','conclusion':'failure'}]}).encode()
        with patch.object(pipeline,'checked_manifest',return_value={}),patch.object(pipeline,'http',return_value=payload):
            with self.assertRaises(ValueError): pipeline.verify_pages(self.run,timeout=0)
        self.assertFalse((self.run/'pages-receipt.json').exists())

    def test_successful_pages_checks_remote_bytes(self):
        write(self.run/'state.json',{'status':'pushed','commit':'abc'})
        payload=json.dumps({'workflow_runs':[{'id':1,'head_sha':'abc','name':'pages build and deployment',
                         'status':'completed','conclusion':'success','html_url':'https://github.com/test/run'}]}).encode()
        with patch.object(pipeline,'checked_manifest',return_value={'files':{'index.html':text_sha('ok\n')}}), \
             patch.object(pipeline,'http',side_effect=[payload,b'ok\r\n']):
            pipeline.verify_pages(self.run,timeout=0)
        self.assertEqual(read(self.run/'state.json')['status'],'pages_verified')

if __name__=='__main__': unittest.main()
