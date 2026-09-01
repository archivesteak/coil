from __future__ import annotations

import re
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
WORKFLOW = REPOSITORY / ".github/workflows/release-host-shards.yml"
ROOT_BUILD = REPOSITORY / "build.gradle.kts"


class ReleaseWorkflowContractTest(unittest.TestCase):
    def test_actions_are_immutably_pinned(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        actions = re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", workflow, re.MULTILINE)
        self.assertTrue(actions)
        for action in actions:
            with self.subTest(action=action):
                self.assertRegex(action, r"^[^@]+@[0-9a-f]{40}$")

    def test_web_release_uses_the_kotlin_pinned_system_toolchain(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0",
            workflow,
        )
        self.assertIn('node-version: "24.10.0"', workflow)
        self.assertIn("npm install --global yarn@1.22.22", workflow)
        self.assertIn('test "$(yarn --version)" = 1.22.22', workflow)
        self.assertEqual(
            workflow.count('"-Pcoil.webToolchain.download=$WEB_TOOLCHAIN_DOWNLOAD"'),
            2,
        )

        build = ROOT_BUILD.read_text(encoding="utf-8")
        self.assertIn('gradleProperty("coil.webToolchain.download")', build)
        self.assertIn("extensions.configure<NodeJsEnvSpec>", build)
        self.assertIn("extensions.configure<WasmNodeJsEnvSpec>", build)
        self.assertIn("extensions.configure<YarnRootEnvSpec>", build)
        self.assertIn("extensions.configure<WasmYarnRootEnvSpec>", build)
        self.assertEqual(build.count("download.set(downloadWebToolchain)"), 4)

    def test_web_release_installs_and_probes_native_link_dependencies(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "- name: Install required Linux native development libraries\n"
            "        if: matrix.owner == 'web'",
            workflow,
        )
        self.assertIn("libfontconfig1-dev", workflow)
        self.assertIn("libgl1-mesa-dev", workflow)
        self.assertIn("pkg-config --exists fontconfig", workflow)
        self.assertIn("pkg-config --exists gl", workflow)

    def test_web_release_serializes_browser_and_native_test_workers(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("OWNER: ${{ matrix.owner }}", workflow)
        self.assertIn('if [ "$OWNER" = web ]; then', workflow)
        self.assertIn("arguments+=(--max-workers=1)", workflow)


if __name__ == "__main__":
    unittest.main()
