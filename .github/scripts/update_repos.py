import os
import re
from base64 import b64decode
from html import escape
import requests

USERNAME = "mukhtar-x"
README_PATH = "README.md"

# Precise keyword definitions
CATEGORIES = {
    "AUTOMATION": ["script", "automation", "n8n", "bot", "monitoring"],
    "FULLSTACK": ["fullstack", "nextjs", "react", "node", "express", "hms", "devcollab", "silkshine", "flask"],
    "MOBILE": ["android", "ios", "reactnative", "flutter", "weatherapp"],
    "SCRAPING": ["scraper", "scraping", "leadscraper", "parser"],
    "SYSTEMS": ["assembly", "cpp", "cplusplus", "lowlevel", "gui", "cli", "snake", "railway", "os_"]
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

def normalize_text(text):
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower() if text else ""

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
    for raw_line in readme.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("```"):
            continue
        if re.match(r"^!\[[^]]*\]\([^)]*\)$", line):
            continue

        line = re.sub(r"!\[([^]]*)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"[*_`~]", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^>\s*", "", line)
        line = " ".join(line.split())

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

def repository_matches(repo, keywords):
    normalized_keywords = [normalize_text(keyword) for keyword in keywords]
    normalized_name = normalize_text(repo.get("name"))

    if any(keyword and keyword in normalized_name for keyword in normalized_keywords):
        return True

    searchable_fields = [repo.get("description"), repo.get("homepage")]
    searchable_fields.extend(repo.get("topics", []))
    tokens = {
        normalize_text(token)
        for field in searchable_fields
        for token in re.findall(r"[A-Za-z0-9]+", field or "")
    }
    return any(keyword in tokens for keyword in normalized_keywords if keyword)

def generate_table(repos, category, headers):
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
        readme = summarize_readme(fetch_readme(repo, headers), description)
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
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    all_repos, headers = fetch_repositories()
    user_repos = [r for r in all_repos if not r.get("fork") and r["name"].lower() != USERNAME.lower()]

    # Track processed repositories to prevent category duplication
    assigned_repos = set()

    for cat_name, keywords in CATEGORIES.items():
        matched_repos = []

        for r in user_repos:
            repo_id = r["id"]
            if repo_id in assigned_repos:
                continue

            if repository_matches(r, keywords):
                matched_repos.append(r)
                assigned_repos.add(repo_id)

        pattern = rf"(<!-- {cat_name}-START -->)(.*?)(<!-- {cat_name}-END -->)"

        if re.search(pattern, content, flags=re.DOTALL):
            section_content = generate_table(matched_repos, cat_name, headers)
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

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    update_readme()
