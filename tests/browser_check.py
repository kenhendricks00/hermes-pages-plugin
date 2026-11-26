"""Optional LOCAL Playwright check and README screenshots. No remote browser."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
from pathlib import Path
import tempfile
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pages', ROOT / 'skills/hermes-pages/scripts/hermes_pages.py')
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


def main():
    docs = ROOT / 'docs'
    docs.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='hp-browser-') as temp:
        workspace = Path(temp) / 'workspace'
        pages.setup(workspace)
        handler = partial(SimpleHTTPRequestHandler, directory=str(workspace / 'public'))
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}/welcome.html'
        try:
            with sync_playwright() as playwright:
                # Existing local Edge only. Never download a browser implicitly.
                browser = playwright.chromium.launch(channel='msedge', headless=True)
                context = browser.new_context(viewport={'width': 1440, 'height': 1100}, color_scheme='light')
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(('http://127.0.0.1:', 'file://', 'data:')) else route.abort())
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(url)
                page.wait_for_load_state('networkidle')
                assert page.locator('h1').inner_text() == 'A better home for your answers'
                assert page.locator('main').evaluate('(e) => getComputedStyle(e).maxWidth') == '748px'
                assert page.locator('main').evaluate('(e) => e.clientWidth - parseFloat(getComputedStyle(e).paddingLeft) - parseFloat(getComputedStyle(e).paddingRight)') == 700
                page.screenshot(path=str(docs / 'light.png'), full_page=True)
                page.locator('#theme').click()
                assert page.locator('html').get_attribute('data-theme') == 'dark'
                page.reload()
                assert page.locator('html').get_attribute('data-theme') == 'dark'
                page.screenshot(path=str(docs / 'dark.png'), full_page=True)
                page.locator('#copy').click()
                assert page.locator('#feedback').inner_text() in ('Link copied', 'Copy is unavailable here. Copy the address from your browser.')
                page.evaluate('window.print = () => { window.__printed = true; }')
                page.locator('#print').click()
                assert page.evaluate('window.__printed') is True
                page.emulate_media(media='print')
                assert page.locator('.topbar').evaluate('(e) => getComputedStyle(e).display') == 'none'
                # Actual print/PDF generation, retained only in the temporary directory.
                pdf = page.pdf(path=str(Path(temp) / 'sample.pdf'))
                assert pdf.startswith(b'%PDF')
                page.emulate_media(media='screen')
                phone = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='light', is_mobile=True, device_scale_factor=1)
                phone.add_init_script("delete window.speechSynthesis; delete window.SpeechSynthesisUtterance;")
                mobile = phone.new_page()
                mobile.goto(url)
                mobile.wait_for_load_state('networkidle')
                assert mobile.locator('#listen').is_disabled()
                assert mobile.locator('#listen').inner_text() == 'Listen unavailable'
                assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
                mobile.screenshot(path=str(docs / 'phone.png'), full_page=True)
                brand = browser.new_page(viewport={'width': 1200, 'height': 600}, device_scale_factor=1)
                brand.goto((docs / 'banner.svg').as_uri())
                brand.screenshot(path=str(docs / 'banner.png'))
                assert not errors, errors
                browser.close()
                print('LOCAL Edge headless: content, 700px column, theme toggle/persistence, copy fallback, print action, print CSS, actual PDF bytes, 390px no overflow, unsupported speech fallback, zero page errors: PASS')
                print('Screenshots: docs/light.png, docs/dark.png, docs/phone.png, docs/banner.png')
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
