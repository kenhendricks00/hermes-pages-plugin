"""Real offline tests. Wrangler subprocesses are explicitly mocked."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/hermes-pages/scripts/hermes_pages.py'
spec = importlib.util.spec_from_file_location('pages', SCRIPT)
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


class RenderTests(unittest.TestCase):
    def test_metadata_escape(self):
        result = pages.template('<script>alert(1)</script>', '\" onload=\"bad', '<p>safe</p>')
        self.assertNotIn('<script>alert', result)
        self.assertIn('&lt;script&gt;', result)
        self.assertIn('&quot; onload=&quot;bad', result)

    def test_one_pass_tokens(self):
        result = pages.template('{{CONTENT}}', '{{TITLE}}', '<p>{{TITLE}}</p>')
        self.assertIn('<p>{{TITLE}}</p>', result)
        self.assertIn('<h1>{{CONTENT}}</h1>', result)

    def test_markdown_html_escape(self):
        result = pages.markdown('<img src=x onerror=evil>\n<script>bad</script>')
        self.assertNotIn('<img', result)
        self.assertNotIn('<script>', result)

    def test_links(self):
        result = pages.markdown('[safe](https://example.org/?a=1&b=2) [unsafe](javascript:evil) [data](data:text/html,evil)')
        self.assertIn('href="https://example.org/?a=1&amp;b=2"', result)
        self.assertNotIn('href="javascript:', result)
        self.assertNotIn('href="data:', result)

    def test_code_and_lists(self):
        result = pages.markdown('## Heading\n\n- one\n- two\n\n1. three\n\n```html\n<script>x</script>\n```\n> quote\n\n`x` and **bold**')
        for value in ('<h2>Heading</h2>', '<ul>', '<ol>', '&lt;script&gt;', '<blockquote>', '<code>x</code>', '<strong>bold</strong>'):
            self.assertIn(value, result)

    def test_table(self):
        result = pages.markdown('| Item | State |\n| --- | --- |\n| X | ready |')
        self.assertIn('<table>', result)
        self.assertIn('<td>ready</td>', result)

    def test_unclosed_fence(self):
        self.assertIn('<pre><code>x</code></pre>', pages.markdown('```\nx'))

    def test_wide(self):
        self.assertIn('<body class="wide">', pages.template('t', 's', 'c', True))


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hp-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'workspace'

    def initialize(self):
        return pages.setup(self.root)

    def test_setup_assets(self):
        sample = self.initialize()
        self.assertTrue(sample.is_file())
        for name in ('theme.css', 'page.js', 'icon.svg', '_headers', 'index.html', 'pages.json', '404.html'):
            self.assertTrue((self.root / 'public' / name).is_file())

    def test_setup_idempotent(self):
        self.initialize()
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.initialize()
        after = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_setup_existing_unmanaged_refuses_preflight(self):
        public = self.root / 'public'
        public.mkdir(parents=True)
        (public / 'theme.css').write_text('mine')
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            self.initialize()
        self.assertEqual((public / 'theme.css').read_text(), 'mine')
        self.assertFalse((public / 'page.js').exists())

    def test_setup_preserves_unrelated(self):
        self.root.mkdir()
        (self.root / 'keep.txt').write_text('personal')
        self.initialize()
        self.assertEqual((self.root / 'keep.txt').read_text(), 'personal')

    def test_render_and_exact_repeat(self):
        self.initialize()
        first = pages.render(self.root, '# Hi', 'Test', slug='test')
        before = (self.root / pages.MARKER).read_bytes()
        self.assertEqual(first, pages.render(self.root, '# Hi', 'Test', slug='test'))
        self.assertEqual(before, (self.root / pages.MARKER).read_bytes())
        self.assertEqual(len(json.loads((self.root / 'public/pages.json').read_text())), 2)

    def test_collision_and_replace(self):
        self.initialize()
        pages.render(self.root, 'One', 'Title', slug='note')
        with self.assertRaisesRegex(ValueError, 'Slug already'):
            pages.render(self.root, 'Two', 'Title', slug='note')
        pages.render(self.root, 'Two', 'Updated', slug='note', replace=True)
        entries = json.loads((self.root / 'public/pages.json').read_text())
        self.assertEqual(sum(e['slug'] == 'note' for e in entries), 1)
        self.assertEqual(entries[0]['title'], 'Updated')
        self.assertIn('Two', (self.root / 'public/note.html').read_text())

    def test_edited_managed_refused(self):
        self.initialize()
        (self.root / 'public/index.html').write_text('edited')
        with self.assertRaisesRegex(ValueError, 'edited'):
            pages.render(self.root, 'New', 'New')
        self.assertFalse((self.root / 'public/new.html').exists())

    def test_unmanaged_slug_refused(self):
        self.initialize()
        (self.root / 'public/note.html').write_text('mine')
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            pages.render(self.root, 'New', 'New', slug='note', replace=True)
        self.assertEqual((self.root / 'public/note.html').read_text(), 'mine')

    def test_bad_slugs(self):
        self.initialize()
        for slug in ('../escape', '/escape', 'index', '404', 'a;echo', 'A', 'a/b', 'x' * 65, 'a\\b', 'é'):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                pages.render(self.root, 'x', 't', slug=slug)

    def test_missing_setup(self):
        with self.assertRaisesRegex(ValueError, 'setup'):
            pages.render(self.root, 'x', 't')

    def test_bad_manifest(self):
        self.initialize()
        (self.root / pages.MARKER).write_text('{')
        with self.assertRaises(ValueError):
            pages.render(self.root, 'x', 't')

    def test_lock(self):
        self.initialize()
        (self.root / '.hermes-pages.lock').write_text('')
        with self.assertRaisesRegex(ValueError, 'busy'):
            pages.render(self.root, 'x', 't')

    def test_symlink(self):
        self.initialize()
        (self.root / 'public/escape.html').unlink(missing_ok=True)
        try:
            (self.root / 'public/escape.html').symlink_to(self.root / 'public/index.html')
        except OSError:
            self.skipTest('OS does not permit symlink creation for this user')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            pages.render(self.root, 'x', 't', slug='escape')

    def test_path_guard(self):
        for name in ('../x', '/x', 'C:/x', 'a\\b'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                pages.safe_path(self.root, name)

    def test_trusted_html_and_unicode(self):
        self.initialize()
        result = pages.render(self.root, '<div class="card">café 文</div>', '文', slug='unicode', html_input=True)
        self.assertIn('<div class="card">café 文</div>', result.read_text(encoding='utf-8'))

    def test_setup_keeps_existing_pages(self):
        self.initialize()
        pages.render(self.root, 'Note', 'Note')
        self.initialize()
        self.assertEqual(len(pages.state(self.root)['pages']), 2)

    def test_deploy_dry_run_no_credentials_or_unmanaged_files(self):
        self.initialize()
        (self.root / 'public/.env').write_text('SECRET=never-upload')
        (self.root / 'public/private.html').write_text('private')
        (self.root / 'auth.json').write_text('never-read')
        with patch.object(pages.subprocess, 'run') as run, patch.object(pages.shutil, 'which') as which:
            result = pages.publish(self.root, 'new-demo', dry_run=True)
        run.assert_not_called()
        which.assert_not_called()
        self.assertTrue(result['dry_run'])
        self.assertNotIn('.env', result['files'])
        self.assertNotIn('private.html', result['files'])
        self.assertNotIn('never-upload', json.dumps(result))

    def test_deploy_subprocess_mocked(self):
        self.initialize()
        def fake_run(command, **kwargs):
            self.assertFalse(kwargs['shell'])
            self.assertEqual(kwargs['timeout'], 180)
            self.assertEqual(command[1:3], ['pages', 'deploy'])
            self.assertEqual(command[-5:], ['--project-name', 'new-demo', '--branch', 'main', '--commit-dirty=true'])
            stage = Path(kwargs['cwd'])
            self.assertTrue((stage / 'public/welcome.html').is_file())
            self.assertFalse((stage / 'functions').exists())
            return subprocess.CompletedProcess(command, 0)
        with patch.object(pages.shutil, 'which', return_value='/approved/wrangler'), patch.object(pages.subprocess, 'run', side_effect=fake_run):
            self.assertTrue(pages.publish(self.root, 'new-demo')['submitted'])

    def test_deploy_error_mocked(self):
        self.initialize()
        with patch.object(pages.shutil, 'which', return_value='/approved/wrangler'), patch.object(pages.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaisesRegex(ValueError, 'exited 1'):
                pages.publish(self.root, 'new-demo')

    def test_missing_wrangler(self):
        self.initialize()
        with patch.object(pages.shutil, 'which', return_value=None), self.assertRaisesRegex(ValueError, 'not found'):
            pages.publish(self.root, 'new-demo')

    def test_deploy_tampered_asset(self):
        self.initialize()
        (self.root / 'public/theme.css').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'changed'):
            pages.publish(self.root, 'new-demo', dry_run=True)

    def test_project_injection(self):
        for project in ('x;echo PWN', '--project', '../x', 'x y', 'Upper', 'x' * 60, 'x-', '-x'):
            with self.subTest(project=project), self.assertRaises(ValueError):
                pages.deploy_command('wrangler', '/tmp/out', project)

    def test_cli_public_confirmation(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            result = pages.main(['--workspace', str(self.root), 'publish', '--project', 'demo'])
        self.assertEqual(result, 1)
        self.assertIn('--confirm-public', output.getvalue())

    def test_cli_real_process(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--workspace', str(self.root), 'setup'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, str(SCRIPT), '--workspace', str(self.root), 'render', '-', '--title', 'CLI note'], input='## hello', capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('<h2>hello</h2>', (self.root / 'public/cli-note.html').read_text())

    def test_cli_missing_file(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--workspace', str(self.root), 'render', str(self.root / 'missing'), '--title', 'x'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Error:', result.stderr)

    def test_profile_workspace(self):
        with patch.dict(os.environ, {'HERMES_HOME': str(self.root)}):
            self.assertEqual(pages.parser().parse_args(['setup']).workspace, self.root / 'hermes-pages')


if __name__ == '__main__':
    unittest.main()
