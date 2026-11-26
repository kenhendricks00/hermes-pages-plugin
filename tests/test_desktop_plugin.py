"""Static checks for the Hermes Desktop half (desktop/plugin.js). No Node needed."""
import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / 'desktop' / 'plugin.js'
ALLOWED = {'@hermes/plugin-sdk', 'react', 'react/jsx-runtime'}


def strip_comments(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'(?m)^\s*//.*$', '', src)


class DesktopPluginStatic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = PLUGIN.read_text(encoding='utf-8')
        cls.code = strip_comments(cls.src)

    def test_imports_only_sdk_and_react(self):
        specs = re.findall(r'''^\s*import\b[^'"]*['"]([^'"]+)['"]''', self.code, flags=re.M)
        self.assertTrue(specs)
        self.assertEqual(set(specs) - ALLOWED, set())
        self.assertNotRegex(self.code, r'\bimport\s*\(')
        self.assertNotRegex(self.code, r'\brequire\s*\(')

    def test_no_jsx_syntax(self):
        # Element literals like <div or <Button in code would not parse uncompiled.
        code = re.sub(r'`[^`]*`', '``', self.code, flags=re.S)
        code = re.sub(r"'(?:[^'\\\n]|\\.)*'", "''", code)
        code = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', code)
        code = re.sub(r'(?<![\w)\]])/(?:[^/\\\n\[]|\\.|\[(?:[^\]\\\n]|\\.)*\])+/[a-z]*', '/re/', code)
        self.assertNotRegex(code, r'(?:return|\(|=|,|\?|:)\s*<[A-Za-z]')

    def test_no_hardcoded_colors(self):
        self.assertNotRegex(self.code, r'#[0-9a-fA-F]{3,8}\b(?![\w-])(?=[;,)\s"\'`}])')
        self.assertNotRegex(self.code, r'\b(?:rgba?|hsla?|oklch|oklab)\s*\(')
        self.assertNotRegex(self.code, r'(?i):\s*(?:black|white|red|blue|green|gray|grey)\b')

    def test_stays_inside_sdk_surface(self):
        for bad in (r'\bwindow\s*\.\s*hermesDesktop', r'(?<![\w$.])eval\(', r'new\s+Function\(',
                    r'document\.querySelector', r'createElement\(\s*[\'"]script', r'[\'"`]<script'):
            self.assertNotRegex(self.code, bad)

    def test_registers_route_nav_and_palette(self):
        self.assertIn("const ROUTE = '/pages'", self.src)
        for area in ('ROUTES_AREA', 'SIDEBAR_NAV_AREA', 'PALETTE_AREA'):
            self.assertRegex(self.code, rf'area:\s*{area}')
        self.assertIn("label: 'Pages'", self.src)
        self.assertIn("label: 'Open Pages'", self.src)
        self.assertIn("id: ID", self.src)
        self.assertIn("const ID = 'hermes-pages'", self.src)

    def test_reads_both_layouts_without_writing(self):
        self.assertIn("['public/', '']", self.src)
        for write in ('writeText', 'rename', 'trash'):
            self.assertNotIn(f'files.{write}', self.code)


if __name__ == '__main__':
    unittest.main()
