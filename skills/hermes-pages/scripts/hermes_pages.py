#!/usr/bin/env python3
"""Offline-first response pages. Python 3.10+, standard library only."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
MARKER = '.hermes-pages.json'
VERSION = '1.0.0'


def escaped(value):
    return html.escape(str(value), quote=True)


def inline(text):
    """Escape everything first. Only explicit http(s)/mailto links become anchors."""
    pattern = r'(`[^`]+`|\[[^\]\n]+\]\([^\s)]+\)|\*\*[^*]+\*\*)'
    result = []
    for part in re.split(pattern, text):
        if part.startswith('`') and part.endswith('`'):
            result.append('<code>' + escaped(part[1:-1]) + '</code>')
        elif part.startswith('**') and part.endswith('**'):
            result.append('<strong>' + escaped(part[2:-2]) + '</strong>')
        elif re.fullmatch(r'\[([^\]\n]+)\]\(([^\s)]+)\)', part):
            match = re.fullmatch(r'\[([^\]\n]+)\]\(([^\s)]+)\)', part)
            label, url = match.groups()
            parsed = urlsplit(url)
            if parsed.scheme.lower() in ('https', 'http', 'mailto'):
                result.append(f'<a href="{escaped(url)}" rel="noreferrer">{escaped(label)}</a>')
            else:
                result.append(escaped(part))
        else:
            result.append(escaped(part))
    return ''.join(result)


def markdown(source):
    """Small documented Markdown subset, not CommonMark. Raw HTML stays text."""
    lines = source.splitlines()
    output = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith('```'):
            i += 1
            code = []
            while i < len(lines) and not lines[i].startswith('```'):
                code.append(lines[i]); i += 1
            output.append('<pre><code>' + escaped('\n'.join(code)) + '</code></pre>')
            i += 1
            continue
        heading = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading:
            level = len(heading[1])
            output.append(f'<h{level}>{inline(heading[2])}</h{level}>')
        elif line.strip() in ('---', '***'):
            output.append('<hr>')
        elif i + 1 < len(lines) and '|' in line and re.fullmatch(r'\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*', lines[i + 1]):
            cells = lambda row: [c.strip() for c in row.strip().strip('|').split('|')]
            output.append('<div class="table-wrap"><table><thead><tr>' + ''.join('<th>' + inline(c) + '</th>' for c in cells(line)) + '</tr></thead><tbody>')
            i += 2
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                output.append('<tr>' + ''.join('<td>' + inline(c) + '</td>' for c in cells(lines[i])) + '</tr>')
                i += 1
            output.append('</tbody></table></div>')
            continue
        elif re.match(r'^\s*([-*]|\d+\.)\s+', line):
            ordered = bool(re.match(r'^\s*\d+\.', line))
            tag = 'ol' if ordered else 'ul'
            output.append('<' + tag + '>')
            pattern = r'^\s*\d+\.\s+' if ordered else r'^\s*[-*]\s+'
            while i < len(lines) and re.match(pattern, lines[i]):
                output.append('<li>' + inline(re.sub(pattern, '', lines[i])) + '</li>'); i += 1
            output.append('</' + tag + '>')
            continue
        elif line.startswith('> '):
            output.append('<blockquote>' + inline(line[2:]) + '</blockquote>')
        else:
            output.append('<p>' + inline(line) + '</p>')
        i += 1
    return '\n'.join(output)


def template(title, summary, content, wide=False):
    values = {'TITLE': escaped(title), 'SUMMARY': escaped(summary), 'CONTENT': content, 'WIDE': 'wide' if wide else ''}
    # Single pass: user content containing template tokens is never substituted again.
    return re.sub(r'\{\{(TITLE|SUMMARY|CONTENT|WIDE)\}\}', lambda m: values[m[1]], (ASSETS / 'response.html').read_text(encoding='utf-8'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(p in ('.', '..') for p in path.parts) or '\\' in relative or ':' in relative:
        raise ValueError('Unsafe workspace path')
    target = root / path
    for item in (target, *target.parents):
        if item.is_symlink():
            raise ValueError('Workspace symlinks are not supported')
        if item == root:
            break
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path leaves workspace')
    return target


@contextmanager
def locked(root):
    if root.is_symlink():
        raise ValueError('Workspace must not be a symlink')
    root.mkdir(parents=True, exist_ok=True)
    lock = root / '.hermes-pages.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Workspace busy; if a previous process crashed, inspect and remove .hermes-pages.lock') from None
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def state(root, required=True):
    marker = safe_path(root, MARKER)
    if not marker.exists():
        if required:
            raise ValueError('Run setup for this dedicated workspace first')
        return {'version': VERSION, 'managed': {}, 'pages': []}
    data = json.loads(marker.read_text(encoding='utf-8'))
    if data.get('version') != VERSION or not isinstance(data.get('managed'), dict) or not isinstance(data.get('pages'), list):
        raise ValueError('Invalid workspace manifest')
    return data


def write_batch(root, data, changes):
    # Preflight all targets before touching any of them. Refuse modified managed files.
    for name, payload in changes.items():
        target = safe_path(root, name)
        if target.exists() and (name not in data['managed'] or digest(target.read_bytes()) != data['managed'][name]):
            raise ValueError(f'Refusing to overwrite unmanaged or edited file: {name}')
    for name, payload in changes.items():
        target = safe_path(root, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(target, payload)
        data['managed'][name] = digest(payload)
    atomic_write(safe_path(root, MARKER), (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode())


def atomic_write(path, payload):
    fd, name = tempfile.mkstemp(prefix='.hp-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def index_changes(data):
    items = ''.join(f'<li><a href="{escaped(p["slug"])}.html">{escaped(p["title"])}</a><p>{escaped(p["summary"])}</p></li>' for p in data['pages'])
    return {'public/index.html': template('Your pages, ready to share', 'A quiet home for useful answers. Render locally. Publish only when you choose.', '<h2>Library</h2><ul class="library">' + items + '</ul>').encode(), 'public/pages.json': (json.dumps(data['pages'], indent=2, ensure_ascii=False) + '\n').encode()}


def setup(root):
    with locked(root):
        data = state(root, required=False)
        changes = {}
        for name in ('theme.css', 'page.js', 'icon.svg', '_headers'):
            key = 'public/' + name
            if key not in data['managed']:
                changes[key] = (ASSETS / name).read_bytes()
        if 'public/404.html' not in data['managed']:
            changes['public/404.html'] = template('Page not found', 'This page may have moved or been removed.', '<p><a href="index.html">Return to the library</a></p>').encode()
        if not data['pages']:
            data['pages'] = [{'slug': 'welcome', 'title': 'A better home for your answers', 'summary': 'From a useful thought to a page worth keeping.'}]
            changes['public/welcome.html'] = template(data['pages'][0]['title'], data['pages'][0]['summary'], (ASSETS / 'sample.html').read_text(encoding='utf-8')).encode()
        # Re-running setup does not replace customized assets or reset existing pages.
        for name, payload in index_changes(data).items():
            if name not in data['managed']:
                changes[name] = payload
        write_batch(root, data, changes)
    return root / 'public' / 'welcome.html'


def render(root, source, title, summary='', slug=None, html_input=False, wide=False, replace=False):
    slug = slug or re.sub('[^a-z0-9]+', '-', title.lower()).strip('-')[:64]
    if not slug or not re.fullmatch('[a-z0-9][a-z0-9-]{0,63}', slug) or slug in ('index', '404'):
        raise ValueError('Slug must be 1-64 lowercase ASCII letters, digits or hyphens; index and 404 are reserved')
    with locked(root):
        data = state(root)
        entry = {'slug': slug, 'title': title, 'summary': summary}
        existing = next((p for p in data['pages'] if p['slug'] == slug), None)
        page = template(title, summary, source if html_input else markdown(source), wide).encode()
        name = f'public/{slug}.html'
        if existing and not replace:
            if existing == entry and safe_path(root, name).read_bytes() == page:
                return root / name
            raise ValueError('Slug already exists. Use --replace to update this managed page')
        data['pages'] = [entry] + [p for p in data['pages'] if p['slug'] != slug]
        changes = index_changes(data)
        changes[name] = page
        write_batch(root, data, changes)
    return root / name


def deploy_command(wrangler, directory, project):
    if not re.fullmatch('[a-z0-9][a-z0-9-]{0,57}[a-z0-9]|[a-z0-9]', project):
        raise ValueError('Project name must be 1-59 lowercase letters, digits or hyphens')
    return [wrangler, 'pages', 'deploy', str(directory), '--project-name', project, '--branch', 'main', '--commit-dirty=true']


def publish(root, project, wrangler='wrangler', dry_run=False):
    # Only managed public files go to a fresh, isolated deployment cwd. Never deploy
    # the workspace itself, external functions directories, credentials or arbitrary files.
    deploy_command(wrangler, 'public', project)
    with locked(root), tempfile.TemporaryDirectory(prefix='hermes-pages-deploy-') as staging:
        data = state(root)
        stage = Path(staging)
        public = stage / 'public'
        public.mkdir()
        for name, expected in data['managed'].items():
            if not name.startswith('public/'):
                continue
            target = safe_path(root, name)
            payload = target.read_bytes()
            if digest(payload) != expected:
                raise ValueError(f'Managed file changed: {name}')
            relative = name.removeprefix('public/')
            # This tool only creates flat static assets. Never admit executable upload hooks.
            if '/' in relative or relative.startswith('.') or relative in ('_worker.js', 'wrangler.toml', 'wrangler.json', 'wrangler.jsonc') or not re.fullmatch(r'[a-zA-Z0-9_-]+\.(html|css|js|svg|json)|_headers', relative):
                raise ValueError('Unexpected deployment asset')
            (public / relative).write_bytes(payload)
        command = deploy_command(wrangler, public, project)
        if dry_run:
            return {'dry_run': True, 'command': deploy_command(wrangler, '<isolated-public-directory>', project), 'files': sorted(p.name for p in public.iterdir())}
        executable = shutil.which(wrangler)
        if not executable:
            raise ValueError('Wrangler not found. Install it locally yourself, then pass --wrangler /path/to/executable; no automatic install')
        command[0] = executable
        completed = subprocess.run(command, cwd=stage, shell=False, timeout=180, check=False)
        if completed.returncode:
            raise ValueError(f'Wrangler exited {completed.returncode}; check its output. No deployment is claimed')
        return {'submitted': True, 'project': project, 'verification': 'Read the deployment URL from Wrangler, then fetch that exact URL before sharing. Success is not URL verification.'}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, default=Path(os.environ.get('HERMES_HOME', str(Path.home() / '.hermes'))) / 'hermes-pages')
    sub = p.add_subparsers(dest='action', required=True)
    sub.add_parser('setup', help='Scaffold only, no network or installs')
    sub.add_parser('guide', help='Print explicit, user-run Cloudflare onboarding steps')
    r = sub.add_parser('render', help='Render locally, never publish')
    r.add_argument('input', help='UTF-8 file or - for stdin')
    r.add_argument('--title', required=True)
    r.add_argument('--summary', default='')
    r.add_argument('--slug')
    r.add_argument('--html', action='store_true', help='Trusted HTML, not sanitized')
    r.add_argument('--wide', action='store_true')
    r.add_argument('--replace', action='store_true')
    d = sub.add_parser('publish', help='Explicitly upload managed public assets with Wrangler')
    d.add_argument('--project', required=True)
    d.add_argument('--wrangler', default='wrangler')
    d.add_argument('--confirm-public', action='store_true')
    d.add_argument('--dry-run', action='store_true')
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    try:
        root = args.workspace.expanduser().absolute()
        if args.action == 'setup':
            print(setup(root))
        elif args.action == 'guide':
            print('1. Choose a NEW dedicated static Pages project and a free Cloudflare account.\n2. Use an existing Wrangler executable or manually install Wrangler in a local tools directory.\n3. In your own interactive terminal: wrangler login (Cloudflare OAuth). Never paste tokens into chat.\n4. wrangler pages project create YOUR-NEW-PROJECT --production-branch main\n5. Review every page in this workspace. Public URLs are not access control.\n6. Run publish --project YOUR-NEW-PROJECT --dry-run, then publish with --confirm-public.\n7. Fetch the exact URL Wrangler reports before sharing. A custom domain is optional and may cost money.\nNo DNS, account settings or paid resources are changed by setup/render.')
        elif args.action == 'render':
            source = sys.stdin.read() if args.input == '-' else Path(args.input).read_text(encoding='utf-8-sig')
            print(render(root, source, args.title, args.summary, args.slug, args.html, args.wide, args.replace))
        elif args.action == 'publish':
            if not args.dry_run and not args.confirm_public:
                raise ValueError('Publishing makes ALL managed pages and the library public. Review them and pass --confirm-public')
            print(json.dumps(publish(root, args.project, args.wrangler, args.dry_run), indent=2))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
