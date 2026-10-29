"""3DS GitHub watcher: finds recently updated Nintendo 3DS repos, summarizes changes with Google Gemini (free tier), notifies via Telegram."""
import os
import re
import json
import html
from datetime import datetime, timedelta, timezone

import time

import requests

# ------------------------------------------------------------------
# SETTINGS YOU CAN EDIT
# ------------------------------------------------------------------
# Each line is one GitHub search. Add or remove terms freely.
SEARCH_TERMS = [
    "3ds in:name,description,topics",
    "topic:nintendo-3ds",
    "topic:3ds",
    "3dsx in:name,description,readme",
    "libctru in:readme",
    "citro3d in:readme",
    "devkitpro 3ds in:readme",
    "luma3ds in:name,description,readme",
    "citra in:name,description",
    "new3ds in:name,description",
]
MODEL = "gemini-3.5-flash-lite"   # lightweight model with a more generous free tier
STATE_FILE = "state.json"
# ------------------------------------------------------------------

GH_TOKEN = os.environ["GH_TOKEN"]
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_KEY = os.environ["GEMINI_API_KEY"]

GH_HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def gh(path, params=None, raw=False):
    headers = dict(GH_HEADERS)
    if raw:
        headers["Accept"] = "application/vnd.github.raw+json"
    r = requests.get(f"https://api.github.com{path}", headers=headers, params=params, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.text if raw else r.json()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_run": None, "repos": {}}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def find_candidates(since):
    found = {}
    for term in SEARCH_TERMS:
        q = f"{term} pushed:>{iso(since)}"
        try:
            data = gh("/search/repositories", {"q": q, "sort": "updated", "per_page": 100})
        except Exception as e:
            print(f"Search failed for '{term}': {e}")
            continue
        for item in data.get("items", []):
            found[item["full_name"]] = item
    print(f"Found {len(found)} candidate repos")
    return found


def get_changes(full_name, since):
    commits = gh(f"/repos/{full_name}/commits", {"since": iso(since), "per_page": 30}) or []
    messages = [c["commit"]["message"].split("\n")[0] for c in commits]
    releases = gh(f"/repos/{full_name}/releases", {"per_page": 5}) or []
    new_releases = [
        r for r in releases
        if not r.get("draft") and r.get("published_at")
        and datetime.fromisoformat(r["published_at"].replace("Z", "+00:00")) >= since
    ]
    return messages, new_releases


def ask_ai(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    for attempt in range(3):
        r = requests.post(url, headers={"x-goog-api-key": GEMINI_KEY}, json=body, timeout=60)
        if r.status_code == 429:  # free-tier rate limit: wait and retry
            time.sleep(20 * (attempt + 1))
            continue
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        match = re.search(r"\{.*\}", text, re.S)
        return json.loads(match.group(0))
    raise RuntimeError("Gemini rate limit hit")


def analyze(item, known, messages, new_releases):
    full_name = item["full_name"]
    if known:
        context = f"Previously known description: {known['description']}"
    else:
        readme = gh(f"/repos/{full_name}/readme", raw=True) or ""
        context = (
            f"GitHub description: {item.get('description')}\n"
            f"Topics: {item.get('topics')}\n"
            f"README (truncated):\n{readme[:3000]}"
        )
    release_text = "\n\n".join(
        f"Release {r['tag_name']} ({r.get('name')}):\n{(r.get('body') or '')[:1500]}"
        for r in new_releases
    ) or "None"
    commit_text = "\n".join(f"- {m}" for m in messages) or "None"

    prompt = f"""You monitor GitHub for projects related to the Nintendo 3DS console: homebrew apps, games, custom firmware, emulators, modding or hacking tools, ports, development libraries. Many such repos never write "Nintendo", so judge from the content.
Note: "3ds" can also mean 3D Studio Max / .3ds model files or 3-D Secure payments. Those are NOT relevant unless the project is clearly for the Nintendo 3DS.

Repository: {full_name}
{context}

Commits in the last few hours:
{commit_text}

New releases:
{release_text}

Reply with ONLY a JSON object:
{{"relevant": true/false, "what_it_is": "1-2 sentence description of the project", "what_changed": "1-2 sentence plain-language summary of the recent changes", "release_summary": "short summary of release notes, or empty string if no release"}}"""
    return ask_ai(prompt)


def send(text):
    if not (TG_TOKEN and TG_CHAT):
        print(text)
        return
    r = requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={"chat_id": TG_CHAT, "text": text[:4000], "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=30,
    )
    if not r.ok:
        print("Telegram error:", r.text)


def main():
    now = datetime.now(timezone.utc)
    state = load_state()
    since = (datetime.fromisoformat(state["last_run"]) if state["last_run"]
             else now - timedelta(hours=6))
    print(f"Checking changes since {iso(since)}")

    notified = 0
    for full_name, item in find_candidates(since).items():
        known = state["repos"].get(full_name)
        if known and not known["relevant"]:
            continue  # already judged not about the 3DS

        try:
            messages, new_releases = get_changes(full_name, since)
            if not messages and not new_releases:
                continue
            result = analyze(item, known, messages, new_releases)
        except Exception as e:
            print(f"Skipping {full_name}: {e}")
            continue

        if not known:
            state["repos"][full_name] = {
                "relevant": bool(result.get("relevant")),
                "description": result.get("what_it_is", ""),
            }
        if not result.get("relevant"):
            continue

        e = html.escape
        lines = [
            f"🎮 <b>{e(full_name)}</b>",
            e(state["repos"][full_name]["description"]),
            "",
            f"<b>Changes:</b> {e(result.get('what_changed', ''))}",
        ]
        for r in new_releases:
            lines.append(f"\n🚀 <b>New release {e(r['tag_name'])}</b>: {e(result.get('release_summary', ''))}")
            lines.append(r["html_url"])
        lines.append(f"\n{item['html_url']}")
        send("\n".join(lines))
        notified += 1

    state["last_run"] = iso(now)
    save_state(state)
    print(f"Done. {notified} notifications sent.")


if __name__ == "__main__":
    main()
