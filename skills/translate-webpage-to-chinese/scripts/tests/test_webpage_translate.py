from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "webpage_translate.py"
SOURCE_URL = "https://example.com/articles/agents/"
HTML = """<!doctype html>
<html lang="en">
<head>
  <title>Agent Guide</title>
  <link rel="stylesheet" href="/assets/site.css">
  <style>.hero { color: red; }</style>
</head>
<body>
  <main class="hero">
    <h1>Build reliable Agents</h1>
    <p>Use an LLM with clear guardrails.</p>
    <p>Use an LLM with clear guardrails.</p>
    <img src="diagram.png" alt="Agent workflow diagram">
    <pre><code>agent.run(input)</code></pre>
  </main>
  <script>window.label = "Do not translate";</script>
</body>
</html>
"""


class WebpageTranslateTest(unittest.TestCase):
    def run_script(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            check=check,
            text=True,
            capture_output=True,
        )

    def test_prepare_apply_and_validate_preserve_structure_and_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input.html"
            work = root / "work"
            output = root / "index.zh-CN.html"
            translations_path = work / "translations.json"
            source.write_text(HTML, encoding="utf-8")

            self.run_script(
                "prepare",
                "--input-html",
                str(source),
                "--source-url",
                SOURCE_URL,
                "--output-dir",
                str(work),
            )
            segments = json.loads((work / "segments.json").read_text(encoding="utf-8"))
            sources = [item["source"] for item in segments]
            self.assertEqual(sources.count("Use an LLM with clear guardrails."), 1)
            self.assertNotIn("agent.run(input)", sources)
            self.assertNotIn('window.label = "Do not translate";', sources)

            translations = {
                item["id"]: {
                    "Agent Guide": "Agent 指南",
                    "Build reliable Agents": "构建可靠的 Agent",
                    "Use an LLM with clear guardrails.": "使用 LLM，并设置清晰的 guardrail。",
                    "Agent workflow diagram": "Agent 工作流示意图",
                }[item["source"]]
                for item in segments
            }
            translations_path.write_text(
                json.dumps(translations, ensure_ascii=False),
                encoding="utf-8",
            )
            self.run_script(
                "apply",
                "--work-dir",
                str(work),
                "--translations",
                str(translations_path),
                "--output",
                str(output),
            )
            self.run_script(
                "validate",
                "--work-dir",
                str(work),
                "--translations",
                str(translations_path),
                "--output",
                str(output),
            )

            result = output.read_text(encoding="utf-8")
            self.assertEqual(result.count("使用 LLM，并设置清晰的 guardrail。"), 2)
            self.assertIn("<code>agent.run(input)</code>", result)
            self.assertIn('window.label = "Do not translate";', result)
            self.assertIn('href="/assets/site.css"', result)
            self.assertIn(f'<base href="{SOURCE_URL}"/>', result)
            self.assertIn(
                'content="script-src \'none\'" data-translation-copy="static"',
                result,
            )
            self.assertIn('lang="zh-CN"', result)

    def test_apply_rejects_missing_translation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input.html"
            work = root / "work"
            translations_path = work / "translations.json"
            source.write_text(HTML, encoding="utf-8")
            self.run_script(
                "prepare",
                "--input-html",
                str(source),
                "--source-url",
                SOURCE_URL,
                "--output-dir",
                str(work),
            )
            translations_path.write_text("{}", encoding="utf-8")
            result = self.run_script(
                "apply",
                "--work-dir",
                str(work),
                "--translations",
                str(translations_path),
                "--output",
                str(root / "out.html"),
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing translations", result.stderr)


if __name__ == "__main__":
    unittest.main()
