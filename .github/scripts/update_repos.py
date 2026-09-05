import os
import re
from base64 import b64decode
from html import escape, unescape
import requests

USERNAME = "mukhtar-x"
README_PATH = "README.md"

CATEGORIES = {
    "AUTOMATION": [
        "script", "automation", "n8n", "bot", "monitoring", "workflow", "cron",
        "webhook", "task", "scheduler", "rpa", "pipeline", "notification",
        "telegrambot", "discordbot", "zapier"
    ],
    "FULLSTACK": [
        "fullstack", "nextjs", "react", "node", "express", "flask", "web",
        "dashboard", "saas", "backend", "frontend", "api", "portal",
        "management", "school", "hospital", "django", "laravel", "php",
        "mongodb", "postgresql", "mysql", "webapp", "ecommerce", "cms",
        "graphql", "vue", "angular", "website"
    ],
    "MOBILE": [
        "android", "ios", "reactnative", "flutter", "mobile", "apk", "swift",
        "kotlin", "crossplatform", "app", "ionic", "expo", "dart",
        "playstore", "appstore"
    ],
    "SCRAPING": [
        "scraper", "scraping", "parser", "crawl", "crawler", "extraction",
        "spider", "extract", "beautifulsoup", "selenium", "puppeteer",
        "playwright", "scrapy", "webscraping"
    ],
    "SYSTEMS": [
        "assembly", "cpp", "cplusplus", "lowlevel", "gui", "cli", "os",
        "system", "kernel", "rust", "embedded", "driver", "golang",
        "compiler", "interpreter", "concurrency", "multithreading"
    ]
}

CATEGORY_DETAILS = {
    "AUTOMATION": {
        "domain": "Automation & workflow engineering",
        "importance": "Reduces repetitive work and improves operational consistency."
    },
    "FULLSTACK": {
        "domain": "Full-stack product engineering",
        "importance": "Connects user experience, business logic, and data into usable systems."
    },
    "MOBILE": {
        "domain": "Mobile application development",
        "importance": "Makes useful software available through focused, accessible experiences."
    },
    "SCRAPING": {
        "domain": "Data extraction & research tooling",
        "importance": "Turns scattered web information into structured, actionable data."
    },
    "SYSTEMS": {
        "domain": "Systems & low-level engineering",
        "importance": "Builds understanding of performance, concurrency, architecture, and fundamentals."
    }
}

# Generic, easily-overloaded words score lower so they can nudge a category
# without single-handedly deciding it (e.g. "app" alone shouldn't outweigh a
# specific hit like "flutter" or "django").
GENERIC_KEYWORDS = {"app", "web", "system", "tool"}
SPECIFIC_KEYWORD_WEIGHT = 3
GENERIC_KEYWORD_WEIGHT = 1

# A README mention counts for less than a name/description/topic hit, since
# READMEs casually reference a lot of adjacent tech (badges, "built with"
# sections, etc.) that isn't really what the project *is*.
README_KEYWORD_WEIGHT = 1
README_SCORE_CHAR_LIMIT = 4000

# The repo's primary language (already returned by the repos API call, no
# extra request needed) is a strong, low-noise signal for the categories
# where the language essentially IS the category. Deliberately left out:
# Python/JavaScript/TypeScript/Java etc., since those show up across almost
# every category and would just add noise here.
LANGUAGE_HINTS = {
    "MOBILE": {"kotlin", "swift", "dart", "objectivec"},
    "SYSTEMS": {"c", "rust", "assembly"},
}
LANGUAGE_HINT_WEIGHT = 4

def normalize_text(text):
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower() if text else ""

def build_field_tokens(text):
    """Split one text field into normalized whole-word tokens, splitting on
    punctuation/whitespace as well as camelCase/PascalCase boundaries."""
    if not text:
        return []
    tokens = []
    for word in re.findall(r"[A-Za-z0-9]+", text):
        parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$|[0-9])|[0-9]+', word)
        for part in (parts or [word]):
            norm = normalize_text(part)
            if norm:
                tokens.append(norm)
    return tokens

def build_match_set(fields):
    """Build a set of exact-match candidates (individual words, plus adjacent
    word-pairs like 'react'+'native' -> 'reactnative') from a list of text
    fields. Matching against this set - instead of checking whether a keyword
    is a *substring* of one giant blob of text - avoids false hits like "api"
    matching inside "capital", or "os" matching inside "hospital"."""
    match_set = set()
    for field in fields:
        tokens = build_field_tokens(field)
        match_set.update(tokens)
        for i in range(len(tokens) - 1):
            match_set.add(tokens[i] + tokens[i + 1])
    return match_set

def strip_code_blocks(text):
    """Remove fenced code blocks so snippets like `import os` or `npm
    install` in a README aren't mistaken for real project description."""
    if not text:
        return ""
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)

def fetch_repositories():
    url = f"https://api.github.com/users/{USERNAME}/repos"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"{USERNAME}-readme-updater",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    repositories = []
    page = 1
    while True:
        response = requests.get(
            url,
            headers=headers,
            params={"sort": "updated", "per_page": 100, "page": page},
            timeout=20,
        )
        response.raise_for_status()
        batch = response.json()
        repositories.extend(batch)
        if len(batch) < 100:
            return repositories, headers
        page += 1

def markdown_text(value):
    return " ".join(str(value or "").split()).replace("|", "\\|")

def html_text(value):
    return escape(" ".join(str(value or "").split()))

def fetch_readme(repo, headers):
    url = f"https://api.github.com/repos/{USERNAME}/{repo['name']}/readme"
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.ok:
            return b64decode(response.json()["content"]).decode("utf-8", errors="replace")
    except (KeyError, ValueError, requests.RequestException):
        pass
    return ""

def summarize_readme(readme, fallback):
    if not readme:
        return fallback

    summary_lines = []
    in_code_block = False
    for raw_line in readme.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"<!--.*?-->", "", line)
        line = re.sub(r"<[^>]+>", "", line)
        if re.match(r"^!\[[^]]*\]\([^)]*\)$", line):
            continue

        line = re.sub(r"!\[([^]]*)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"[*_`~]", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^>\s*", "", line)
        line = " ".join(unescape(line).split())

        if len(line) < 20 or line.lower().startswith(("built with", "contributors", "license:")):
            continue
        summary_lines.append(line)
        if len(summary_lines) == 4:
            break

    summary = " ".join(summary_lines)
    if not summary:
        return fallback
    if len(summary) <= 320:
        return summary
    return summary[:320].rsplit(" ", 1)[0] + "..."

def calculate_repo_scores(repo, readme_text=""):
    name = repo.get("name") or ""
    description = repo.get("description") or ""
    homepage = repo.get("homepage") or ""
    topics = repo.get("topics", [])
    language = normalize_text(repo.get("language") or "")

    core_matches = build_match_set([name, description, homepage] + topics)

    # README content is a secondary signal: code fences are stripped first,
    # and the text is capped so a long README can't drown out the much more
    # deliberate name/description/topics signal.
    readme_clean = strip_code_blocks(readme_text)[:README_SCORE_CHAR_LIMIT]
    readme_matches = build_match_set([readme_clean])

    scores = {cat: 0 for cat in CATEGORIES}
    for cat_name, keywords in CATEGORIES.items():
        for kw in keywords:
            norm_kw = normalize_text(kw)
            if not norm_kw:
                continue
            weight = GENERIC_KEYWORD_WEIGHT if norm_kw in GENERIC_KEYWORDS else SPECIFIC_KEYWORD_WEIGHT
            if norm_kw in core_matches:
                scores[cat_name] += weight
            if norm_kw in readme_matches:
                scores[cat_name] += README_KEYWORD_WEIGHT

    for cat_name, langs in LANGUAGE_HINTS.items():
        if language in langs:
            scores[cat_name] += LANGUAGE_HINT_WEIGHT

    return scores

def generate_table(repos, category, repo_readmes):
    if not repos:
        return ""

    category_detail = CATEGORY_DETAILS[category]
    importance = html_text(category_detail["importance"])
    rows = [
        '<div style="overflow-x:auto;margin-top:0">',
        '<table width="100%" style="border:1px solid #30363d;border-radius:14px;border-collapse:separate;border-spacing:0;overflow:hidden">',
        '<thead><tr>',
        '<th align="left" width="22%">IMAGE</th>',
        '<th align="left" width="48%">PROJECT</th>',
        '<th align="left" width="20%">IMPACT</th>',
        '<th align="left" width="10%">STACK</th>',
        '</tr></thead>',
        '<tbody>'
    ]

    for repo in repos:
        name = html_text(repo["name"])
        url = escape(repo["html_url"], quote=True)
        description = html_text(repo.get("description")) if repo.get("description") else "No description provided."
        readme = summarize_readme(repo_readmes.get(repo["name"], ""), description)
        lang = html_text(repo.get("language") or "Code")
        updated = html_text(repo.get("updated_at", "")[:10] or "Unknown")
        image_url = f"https://opengraph.githubassets.com/1/{USERNAME}/{repo['name']}"

        rows.append(
            f'''<tr>
<td valign="top" style="padding:14px"><a href="{url}"><img src="{image_url}" width="180" height="110" alt="{name} preview" /></a></td>
<td valign="top" style="padding:14px"><p style="margin:0 0 8px;font-size:0.95em"><strong><a href="{url}">{name}</a> <a href="{url}" title="View project" aria-label="View project">&#8599;</a></strong></p><p style="margin:0">{html_text(readme)}</p></td>
<td valign="top" style="padding:14px">{importance}</td>
<td valign="top" style="padding:14px"><code>{lang}</code><br><br><kbd>{updated}</kbd></td>
</tr>'''
        )

    rows.extend(['</tbody>', '</table>', '</div>'])
    return "\n".join(rows)

def update_readme():
    if not os.path.exists(README_PATH):
        print(f"ERROR: {README_PATH} was not found in the current directory.")
        return

    try:
        with open(README_PATH, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"ERROR: Failed to read {README_PATH}: {e}")
        return

    all_repos, headers = fetch_repositories()
    user_repos = [r for r in all_repos if not r.get("fork") and r["name"].lower() != USERNAME.lower()]

    # Fetch each repo's README once. It's used both here - so a project is
    # categorized by what it actually does, not just its repo name - and
    # later for the project table's description text, so we never fetch the
    # same README twice.
    repo_readmes = {r["name"]: fetch_readme(r, headers) for r in user_repos}

    category_matches_map = {cat: [] for cat in CATEGORIES}

    for r in user_repos:
        scores = calculate_repo_scores(r, repo_readmes.get(r["name"], ""))
        best_cat = max(scores, key=scores.get)

        # Only assign if it actually matched at least one keyword (score > 0)
        if scores[best_cat] > 0:
            category_matches_map[best_cat].append(r)

    for cat_name, matched_repos in category_matches_map.items():
        pattern = rf"(<!-- {cat_name}-START -->)(.*?)(<!-- {cat_name}-END -->)"

        if re.search(pattern, content, flags=re.DOTALL):
            section_content = generate_table(matched_repos, cat_name, repo_readmes)
            if not section_content:
                section_content = f"<p>No projects currently match the {cat_name.lower()} category.</p>"
            content = re.sub(
                pattern,
                lambda match: f"{match.group(1)}\n{section_content}\n{match.group(3)}",
                content,
                flags=re.DOTALL,
            )
            print(f"SUCCESS: Injected {cat_name} table into README.md")
        else:
            print(f"WARNING: Tags <!-- {cat_name}-START --> and <!-- {cat_name}-END --> NOT found in README.md!")

    try:
        with open(README_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        print("SUCCESS: README.md updated successfully.")
    except Exception as e:
        print(f"ERROR: Failed to write to {README_PATH}: {e}")

if __name__ == "__main__":
    update_readme()
