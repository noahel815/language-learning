"""Regression tests run only in disposable copies; never overwrite published lessons."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import generate_weekly_japanese as generator


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        shutil.copytree(generator.ROOT, self.root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        self.data = json.loads((self.root / 'generator/weekly-content-2026-W40-recovery.json').read_text(encoding='utf-8'))
        # Remove only the recovery output in this temporary copy to exercise first generation.
        self.output = self.root / 'japanese/JP-V1-2026-W40-D3.html'
        self.output.unlink(missing_ok=True)
        self.input = self.root / 'generator/test-input.json'

    def run_generator(self, *extra):
        self.input.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
        return subprocess.run([sys.executable, str(self.root / 'generator/generate_weekly_japanese.py'), '--content', str(self.input), *extra], capture_output=True, text=True, encoding='utf-8')

    def test_compact_index_links_and_idempotence(self):
        index = self.root / 'index.html'
        index.write_text('<main><section><a href="old.html">Old</a></section></main>', encoding='utf-8')
        result = self.run_generator()
        self.assertEqual(result.returncode, 0, result.stderr)
        first = index.read_bytes()
        self.assertIn(b'JP-V1-2026-W40-D3.html', first)
        self.assertIn(b'old.html', first)
        self.assertEqual(self.run_generator().returncode, 0)
        self.assertEqual(index.read_bytes(), first)

    def test_previous_managed_links_preserved(self):
        text = '<main><section id="this-week"><h2>Old</h2><a href="old.html">Old</a></section></main>'
        result = generator.render_index(text, self.data['lessons'])
        self.assertIn('old.html', result)
        self.assertEqual(result.count('id="this-week"'), 1)

    def test_date_mismatch_no_writes(self):
        self.data['lessons'][0]['lesson']['date'] = '2026-10-01'
        before = (self.root / 'index.html').read_bytes()
        self.assertNotEqual(self.run_generator().returncode, 0)
        self.assertFalse(self.output.exists())
        self.assertEqual((self.root / 'index.html').read_bytes(), before)

    def test_frozen_change_no_writes(self):
        with (self.root / 'templates/japanese-lesson-v1.html').open('a') as handle:
            handle.write('changed')
        self.assertNotEqual(self.run_generator().returncode, 0)
        self.assertFalse(self.output.exists())

    def test_git_lf_template_baseline(self):
        for name in ['japanese-lesson-v1.html', 'JAPANESE_TEMPLATE_V1.md']:
            path = self.root / 'templates' / name
            path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
        result = self.run_generator()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_qa_failure_no_writes(self):
        self.data['lessons'][0]['lesson']['trendSource'] = 'invalid'
        before = (self.root / 'index.html').read_bytes()
        self.assertNotEqual(self.run_generator().returncode, 0)
        self.assertFalse(self.output.exists())
        self.assertEqual((self.root / 'index.html').read_bytes(), before)

    def test_existing_lesson_requires_opt_in(self):
        self.output.write_text('published baseline', encoding='utf-8')
        self.assertNotEqual(self.run_generator().returncode, 0)
        self.assertEqual(self.output.read_text(), 'published baseline')

    def test_full_week_still_supported(self):
        self.data = json.loads((self.root / 'generator/sample-weekly-content.json').read_text(encoding='utf-8'))
        for item in self.data['lessons']:
            (self.root / ('japanese/' + item['lesson']['id'] + '.html')).unlink(missing_ok=True)
        result = self.run_generator()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(all((self.root / ('japanese/' + x['lesson']['id'] + '.html')).exists() for x in self.data['lessons']))


if __name__ == '__main__':
    unittest.main()
