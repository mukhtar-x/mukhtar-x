import os
import re
import requests

USERNAME = "mukhtar-x"
README_PATH = "README.md"

# Maps your custom README comment tags to language/topic keywords in your repos
CATEGORIES = {
    "AUTOMATION": ["script", "automation", "n8n", "bot", "monitoring"],
    "FULLSTACK": ["fullstack", "next", "react", "node", "express", "web", "hms", "devcollab"],
    "MOBILE": ["mobile", "android", "ios", "react-native", "weather"],
    "SCRAPING": ["scraper", "scraping", "lead", "dom", "parser"],
    "SYSTEMS": ["assembly", "c++", "c", "low-level", "gui", "cli", "snake", "railway"]
}

def fetch_repositories():
    url = f"https://api.github.com/users/{USERNAME}/repos?sort=updated&per_page=100"
    headers = {}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch repos: {response.status_code}")
    return response.json()

def generate_table(repos):
    if not repos:
        return ""
        
    rows = [
        "| Interface | Codebase | Architectural Domain | Core Stack |",
        "| :---: | :--- | :--- | :--- |"
    ]
    
    for repo in repos:
        name = repo["name"]
        url = repo["html_url"]
        desc = repo.get("description") or "Automated project repository."
        lang = repo.get("language") or "Code"
        
        row = (
            f'| <a href="{url}"><img src="https://placehold.co/320x190/161b22/A3A3A3.png?text={name}" '
            f'width="160" height="95" alt="{name} Preview" /></a> '
            f'| <a href="{url}"><kbd>{name}</kbd></a> '
            f'| **{name}**<br>{desc} '
            f'| `{lang}` |'
        )
        rows.append(row)
        
    return "\n".join(rows)

def update_readme():
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    all_repos = fetch_repositories()
    
    # Filter out forks or profile repos
    user_repos = [r for r in all_repos if not r.get("fork") and r["name"].lower() != USERNAME.lower()]

    for cat_name, keywords in CATEGORIES.items():
        matched_repos = []
        for r in user_repos:
            repo_text = (r["name"] + " " + (r.get("description") or "")).lower()
            if any(kw in repo_text for kw in keywords):
                matched_repos.append(r)

        if matched_repos:
            table_md = generate_table(matched_repos)
            pattern = rf"(<!-- {cat_name}-START -->)(.*?)(<!-- {cat_name}-END -->)"
            replacement = f"\\1\n{table_md}\n\\3"
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    update_readme()
