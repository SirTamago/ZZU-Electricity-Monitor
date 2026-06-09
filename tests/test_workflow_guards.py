import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def workflow_step(text: str, name: str) -> str:
    marker = f"- name: {name}"
    start = text.index(marker)
    match = re.search(r"\n      - name: ", text[start + len(marker):])
    end = len(text) if match is None else start + len(marker) + match.start()
    return text[start:end]


class WorkflowGuardTests(unittest.TestCase):
    def test_static_decrypt_step_fails_closed(self):
        step = workflow_step(read_workflow("static.yml"), "Decrypt tokens.enc if exists")

        self.assertIn("TOKEN_ENCRYPTION_KEY: ${{ secrets.TOKEN_ENCRYPTION_KEY }}", step)
        self.assertIn("python3 ./crypto.py decrypt", step)
        self.assertNotRegex(step, r"python3\s+\./crypto\.py\s+decrypt\s*\|\|")

    def test_static_runtime_receives_trusted_device_id(self):
        step = workflow_step(read_workflow("static.yml"), "Run python script")

        self.assertIn("ACCOUNT: ${{ secrets.ACCOUNT }}", step)
        self.assertIn("PASSWORD: ${{ secrets.PASSWORD }}", step)
        self.assertIn("ZZU_DEVICE_ID: ${{ secrets.ZZU_DEVICE_ID }}", step)
        self.assertIn("python3 ./main.py", step)
        self.assertIn("python3 ./markdown.py >> $GITHUB_STEP_SUMMARY", step)

    def test_workflows_remove_auth_files_before_pages_artifact(self):
        for workflow in ("static.yml", "redeploy.yml"):
            with self.subTest(workflow=workflow):
                text = read_workflow(workflow)
                remove_step = workflow_step(text, "Remove auth files from workspace and Pages artifact")

                self.assertLess(
                    text.index("- name: Remove auth files from workspace and Pages artifact"),
                    text.index("- name: Upload artifact"),
                )
                self.assertIn("rm -f ./page/data/tokens.json ./page/data/tokens.enc", remove_step)

    def test_page_branch_publish_keeps_frontend_runtime_files(self):
        for workflow in ("static.yml", "redeploy.yml"):
            with self.subTest(workflow=workflow):
                step = workflow_step(read_workflow(workflow), "Commit changes")

                self.assertIn("./page/data", step)
                self.assertIn("./page/main.js", step)
                self.assertIn("./page/style.css", step)
                self.assertNotIn("./page/README.md", step)
                self.assertIn("rm -f pages/data/tokens.json", step)

    def test_page_branch_clone_preserves_room_shards_from_main(self):
        for workflow in ("static.yml", "redeploy.yml"):
            with self.subTest(workflow=workflow):
                step = workflow_step(read_workflow(workflow), "Clone page branch")

                self.assertIn('if [ "$(basename "$item")" = "rooms" ]; then', step)
                self.assertIn("continue", step)

    def test_publish_steps_only_run_on_main_branch(self):
        for workflow, deploy_job in (("static.yml", "deploy"), ("redeploy.yml", "deploy")):
            with self.subTest(workflow=workflow):
                text = read_workflow(workflow)

                self.assertIn("group: pages-${{ github.ref }}", text)
                self.assertIn(f"\n  {deploy_job}:\n    if: github.ref == 'refs/heads/main'", text)

                for step_name in ("git config", "Commit changes", "Upload artifact"):
                    step = workflow_step(text, step_name)
                    self.assertIn("if: github.ref == 'refs/heads/main'", step)


if __name__ == "__main__":
    unittest.main()
