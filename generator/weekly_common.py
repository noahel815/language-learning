"""Shared, dependency-free guards for the weekly Candidate pipeline."""
import hashlib
import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

VERSION = 'Japanese Lesson Template V1'
DATA_SOURCE = 'collection://399114a6-0358-4421-964e-f300470ea2fa'

def require(ok, message):
    if not ok:
        raise ValueError(message)

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    temp.replace(path)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def text_sha(text):
    return hashlib.sha256(text.replace('\r\n', '\n').encode('utf-8')).hexdigest()

def lesson_id(day):
    y, w, d = day.isocalendar()
    return f'JP-V1-{y}-W{w:02d}-D{d}'

def frozen(root):
    for name, allowed in read(root / 'generator/frozen-hashes.json').items():
        require(sha(root / name) in allowed, 'Frozen baseline changed: ' + name)

def protected(root):
    names = [*root.glob('japanese/*.html'), *root.glob('templates/*')]
    names += [root / 'generator/template-schema.json', root / 'generator/frozen-hashes.json',
              root / 'generator/build_mid_september_content.py']
    return {p.relative_to(root).as_posix(): sha(p) for p in names if p.is_file()}

def unchanged(root, baseline):
    for name, digest in baseline.items():
        require((root / name).is_file() and sha(root / name) == digest, 'Protected file changed: ' + name)
    frozen(root)

def schema_check(value, schema, document=None, at='$'):
    """Evaluate ALL keywords in the frozen V1 schema; unknown keywords fail closed.

    This is intentionally a V1-contract evaluator, not a general JSON Schema library.
    """
    document = document or schema
    supported = {'$schema','$id','title','description','$defs','$ref','type','const','enum',
                 'required','properties','additionalProperties','pattern','format','minLength',
                 'items','minItems','minimum','maximum','allOf','if','then'}
    require(not set(schema) - supported, f'{at}: unsupported schema keyword')
    if '$ref' in schema:
        target = document
        require(schema['$ref'].startswith('#/'), 'External schema refs forbidden')
        for key in schema['$ref'][2:].split('/'):
            target = target[key]
        schema_check(value, target, document, at)
    if 'const' in schema:
        require(value == schema['const'], f'{at}: const mismatch')
    if 'enum' in schema:
        require(value in schema['enum'], f'{at}: enum mismatch')
    types = {'object':dict,'array':list,'string':str,'integer':int,'boolean':bool,'null':type(None)}
    if 'type' in schema:
        kinds = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        require(any(type(value) is types[k] for k in kinds), f'{at}: wrong type')
    if isinstance(value, dict):
        require(set(schema.get('required', [])) <= set(value), f'{at}: missing required properties')
        props = schema.get('properties', {})
        if schema.get('additionalProperties') is False:
            require(not set(value) - set(props), f'{at}: unexpected properties {set(value)-set(props)}')
        for key in value.keys() & props.keys():
            schema_check(value[key], props[key], document, at + '.' + key)
    if isinstance(value, list):
        require(len(value) >= schema.get('minItems', 0), f'{at}: too few items')
        for i, item in enumerate(value):
            if 'items' in schema:
                schema_check(item, schema['items'], document, f'{at}[{i}]')
    if isinstance(value, str):
        require(len(value) >= schema.get('minLength', 0), f'{at}: too short')
        if 'pattern' in schema:
            require(re.search(schema['pattern'], value), f'{at}: pattern mismatch')
        if schema.get('format') == 'date':
            require(date.fromisoformat(value).isoformat() == value, f'{at}: invalid date')
    if type(value) is int:
        require(schema.get('minimum', value) <= value <= schema.get('maximum', value), f'{at}: out of range')
    for rule in schema.get('allOf', []):
        schema_check(value, rule, document, at)
    if 'if' in schema:
        try:
            schema_check(value, schema['if'], document, at)
        except ValueError:
            pass
        else:
            schema_check(value, schema.get('then', {}), document, at)

class SafeFragment(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
    def handle_starttag(self, tag, attrs):
        require(tag in {'ruby','rt','rp','br','p','strong','em'} and not attrs, 'Unsafe content HTML')
        if tag != 'br':
            self.stack.append(tag)
    def handle_endtag(self, tag):
        require(self.stack and self.stack.pop() == tag, 'Unbalanced content HTML')

def safe_fragments(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith('Html'):
                parser = SafeFragment()
                parser.feed(item)
                parser.close()
                require(not parser.stack, 'Unclosed HTML fragment')
            else:
                safe_fragments(item)
    elif isinstance(value, list):
        for item in value:
            safe_fragments(item)

def notion_plan(lessons, rows):
    result = []
    for item in lessons:
        meta = item['lesson']
        y, w, d = date.fromisoformat(meta['date']).isocalendar()
        expected = {'Lesson':meta['id'], 'Chapter':f'{y}-W{w:02d}', 'Lesson No.':d,
                    'date:日期:start':meta['date'], 'date:日期:is_datetime':0,
                    '主題':meta['topicZh'], '程度':'混合',
                    '教材網址':f'https://noahel815.github.io/language-learning/japanese/{meta["id"]}.html'}
        matches = [r for r in rows if r.get('Lesson') == meta['id']]
        require(len(matches) <= 1, 'Duplicate Notion Lesson ID: ' + meta['id'])
        if matches:
            require(all(matches[0].get(k) == v for k,v in expected.items()), 'Conflicting Notion row: ' + meta['id'])
        result.append({'action':'skip' if matches else 'create', 'properties':expected,
                       'createOnly':{'狀態':'未讀','完成':'__NO__','回饋已處理':'__NO__'}})
    return result
