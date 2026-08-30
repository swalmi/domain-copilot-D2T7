import json
import os
import subprocess
import time

GH_TOKEN = os.popen("sed -E 's/.*:(ghp_[^@]+)@.*/\\1/' ~/.git-credentials").read().strip()
env = os.environ.copy()
env["GH_TOKEN"] = GH_TOKEN


def run_gh(args: list[str]) -> str:
    """Execute a GitHub CLI command with authenticated environment token."""
    res = subprocess.run(["gh"] + args, capture_output=True, text=True, env=env)
    if res.returncode != 0:
        print(f"Error running gh {' '.join(args[:3])}...: {res.stderr.strip()[:100]}")
    return res.stdout.strip()


def backfill() -> None:
    """Create matching GitHub issues for past PRs and link them with Closes #issue syntax."""
    prs_raw = run_gh(["pr", "list", "--state", "all", "--limit", "100", "--json", "number,title,body,url"])
    prs = json.loads(prs_raw)
    prs.sort(key=lambda x: x["number"])

    print(f"Found {len(prs)} PRs. Starting issue backfill process...")

    for pr in prs:
        pr_num = pr["number"]
        pr_title = pr["title"]
        pr_body = pr["body"] or ""

        # Skip PRs that already link to an issue via "Closes #"
        if "Closes #" in pr_body or "Fixes #" in pr_body:
            print(f"PR #{pr_num} already links to an issue. Skipping.")
            continue

        # Check existing comments on PR to avoid duplicate issue creation
        comments_raw = run_gh(["pr", "view", str(pr_num), "--json", "comments"])
        try:
            comments_data = json.loads(comments_raw)
            has_closes = any("Closes #" in c.get("body", "") for c in comments_data.get("comments", []))
            if has_closes:
                print(f"PR #{pr_num} already has 'Closes #' in comments. Skipping.")
                continue
        except Exception:
            pass

        # 1. Create Issue
        issue_body = (
            f"## Description\n"
            f"Task issue tracking work for pull request #{pr_num}.\n\n"
            f"### Feature / Task\n"
            f"{pr_title}\n\n"
            f"### Linked Pull Request\n"
            f"Resolved by PR #{pr_num} ({pr['url']})"
        )
        issue_url = run_gh(["issue", "create", "--title", pr_title, "--body", issue_body])
        if not issue_url or "/issues/" not in issue_url:
            print(f"Failed to create issue for PR #{pr_num}")
            continue

        issue_num = issue_url.split("/issues/")[-1]
        print(f"Created Issue #{issue_num} for PR #{pr_num}: '{pr_title}'")

        # 2. Add comment to PR linking the issue
        run_gh(["pr", "comment", str(pr_num), "--body", f"Closes #{issue_num}"])
        print(f"Added comment to PR #{pr_num} with 'Closes #{issue_num}'")

        # 3. Close the issue since PR is already merged
        run_gh(["issue", "close", issue_num, "--reason", "completed"])
        print(f"Closed Issue #{issue_num}")


if __name__ == "__main__":
    backfill()
