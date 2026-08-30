import asyncio
import json
import os
from typing import Any
import urllib.request


GH_TOKEN = os.popen("sed -E 's/.*:(ghp_[^@]+)@.*/\\1/' ~/.git-credentials").read().strip()
REPO = "swalmi/domain-copilot-D2T7"
HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Python",
}


def make_request(url: str, method: str = "GET", data: dict | None = None) -> Any:
    """Execute REST API HTTP request using urllib."""
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data else None,
        headers=HEADERS,
        method=method,
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def process_pr(pr: dict, semaphore: asyncio.Semaphore) -> None:
    """Create matching GitHub issue for PR, comment 'Closes #issue', and close issue."""
    async with semaphore:
        pr_num = pr["number"]
        pr_title = pr["title"]
        pr_body = pr.get("body") or ""

        if "Closes #" in pr_body or "Fixes #" in pr_body:
            print(f"PR #{pr_num} already links to an issue in body. Skipping.")
            return

        loop = asyncio.get_running_loop()

        comments_url = f"https://api.github.com/repos/{REPO}/issues/{pr_num}/comments"
        comments = await loop.run_in_executor(None, make_request, comments_url)
        if any("Closes #" in c.get("body", "") for c in comments):
            print(f"PR #{pr_num} already links to an issue in comments. Skipping.")
            return

        create_issue_url = f"https://api.github.com/repos/{REPO}/issues"
        issue_data = {
            "title": pr_title,
            "body": (
                f"## Description\nTask issue tracking implementation for PR #{pr_num}.\n\n"
                f"### Task / Feature\n{pr_title}\n\n"
                f"### Linked Pull Request\nResolved by PR #{pr_num} ({pr.get('html_url')})"
            ),
        }
        issue = await loop.run_in_executor(
            None, lambda: make_request(create_issue_url, "POST", issue_data)
        )
        issue_num = issue["number"]

        comment_data = {"body": f"Closes #{issue_num}"}
        await loop.run_in_executor(
            None, lambda: make_request(comments_url, "POST", comment_data)
        )

        close_issue_url = f"https://api.github.com/repos/{REPO}/issues/{issue_num}"
        close_data = {"state": "closed", "state_reason": "completed"}
        await loop.run_in_executor(
            None, lambda: make_request(close_issue_url, "PATCH", close_data)
        )
        print(f"Successfully processed PR #{pr_num} -> Linked & Closed Issue #{issue_num}")


async def main() -> None:
    """Fetch all PRs and run concurrent issue backfilling."""
    prs_url = f"https://api.github.com/repos/{REPO}/pulls?state=all&per_page=100"
    prs = make_request(prs_url)
    prs.sort(key=lambda x: x["number"])
    print(f"Fetched {len(prs)} PRs via REST API. Backfilling missing issues...")

    sem = asyncio.Semaphore(5)
    tasks = [process_pr(pr, sem) for pr in prs]
    await asyncio.gather(*tasks)
    print("All past PRs have been linked with corresponding GitHub Issues!")


if __name__ == "__main__":
    from typing import Any
    asyncio.run(main())
