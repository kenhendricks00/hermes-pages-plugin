"""Rebuild the icon PNGs and the README banner with LOCAL headless Edge. No remote browser.

  PYTHONPATH= uv run --no-project --with playwright python tests/make_assets.py

The banner's right column is a real page rendered by hermes_pages.py from the
bundled generic sample into a temporary workspace, captured in dark mode.
"""
import base64
import importlib.util
from pathlib import Path
import tempfile
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pages', ROOT / 'skills/hermes-pages/scripts/hermes_pages.py')
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)

BANNER = """<!doctype html><meta charset="utf-8"><style>
html,body{width:1200px;height:600px;overflow:hidden;margin:0}
body{font-family:'Segoe UI',Inter,Helvetica,Arial,sans-serif;background:radial-gradient(900px 500px at 100% 0,#1b2230,transparent),#0f1013;
display:flex;align-items:center;padding:0 80px;gap:56px;box-sizing:border-box}
.l{flex:1}.l img{width:120px;height:120px}
h1{font-size:64px;margin:46px 0 14px;font-weight:700;color:#f3f4f6;letter-spacing:-.5px}
p{font-size:26px;line-height:1.4;color:#9aa1ae;margin:0;max-width:520px}
.r{width:400px;height:480px;flex:none;border-radius:18px;overflow:hidden;border:1px solid #2a2e37;box-shadow:0 18px 50px rgba(0,0,0,.45)}
.r img{display:block;width:400px}</style>
<div class="l"><img src="ICON"><h1>Hermes Pages</h1><p>Give useful answers a place to live.</p></div>
<div class="r"><img src="PAGE"></div>"""


def main():
    assets, docs = ROOT / 'assets', ROOT / 'docs'
    docs.mkdir(exist_ok=True)
    icon = (assets / 'icon.svg').resolve().as_uri()
    with tempfile.TemporaryDirectory(prefix='hp-assets-') as temp, sync_playwright() as pw:
        workspace = Path(temp) / 'workspace'
        pages.setup(workspace)  # renders the bundled generic sample as welcome.html
        browser = pw.chromium.launch(channel='msedge', headless=True)
        ctx = browser.new_context(device_scale_factor=1)
        ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith(('file://', 'data:')) else r.abort())
        page = ctx.new_page()
        for size in (512, 256, 128, 64):
            page.set_viewport_size({'width': size, 'height': size})
            page.set_content(f'<style>body{{margin:0}}img{{display:block}}</style><img src="{icon}" width="{size}" height="{size}">')
            page.wait_for_timeout(100)
            page.screenshot(path=str(assets / f'icon-{size}.png'), omit_background=True)

        # Real rendered page, dark mode, captured at 2x so it stays crisp at 400px wide.
        dark = browser.new_context(viewport={'width': 400, 'height': 480}, color_scheme='dark', device_scale_factor=2)
        dark.route('**/*', lambda r: r.continue_() if r.request.url.startswith(('file://', 'data:')) else r.abort())
        shot_page = dark.new_page()
        shot_page.goto((workspace / 'public' / 'welcome.html').as_uri())
        shot_page.wait_for_load_state('load')
        shot_page.wait_for_timeout(300)
        png = shot_page.screenshot()
        page_uri = 'data:image/png;base64,' + base64.b64encode(png).decode()

        f = Path(temp) / 'banner.html'
        f.write_text(BANNER.replace('ICON', icon).replace('PAGE', page_uri), encoding='utf-8')
        page.set_viewport_size({'width': 1200, 'height': 600})
        page.goto(f.as_uri())
        page.wait_for_timeout(300)
        page.screenshot(path=str(docs / 'banner.png'))
        browser.close()
    print('Wrote assets/icon-{512,256,128,64}.png, docs/banner.png')


if __name__ == '__main__':
    main()
