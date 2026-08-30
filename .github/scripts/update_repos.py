import os
import re
import requests

USERNAME = "mukhtar-x"
README_PATH = "README.md"

CATEGORIES = {
    "AUTOMATION": ["script", "automation", "n8n", "bot", "monitoring"],
    "FULLSTACK": ["web", "fullstack", "next", "react", "node", "express", "hms", "devcollab", "silkshine"],
    "MOBILE": ["app", "mobile", "android", "ios", "reactnative", "flutter"],
    "SCRAPING": ["scrape", "scraper", "scraping", "lead", "dom", "parser"],
    "SYSTEMS": ["system", "assembly", "cpp", "cplusplus", "lowlevel", "gui", "cli", "snake", "railway"]
}

def normalize_text(text):
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower() if text else ""

def fetch_repositories():
    url = f"https://api.github.com/users/{USERNAME}/repos?sort=updated&per_page=100"
    headers = {"Accept": "application/vnd.github.v3+json"}
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
    user_repos = [r for r in all_repos if not r.get("fork") and r["name"].lower() != USERNAME.lower()]

    print(f"--- Total Public Non-Fork Repos Found: {len(user_repos)} ---")
    for r in user_repos:
        print(f"Discovered Repo: {r['name']}")

    for cat_name, keywords in CATEGORIES.items():
        matched_repos = []
        normalized_keywords = [normalize_text(kw) for kw in keywords]

        for r in user_repos:
            name = normalize_text(r.get("name"))
            desc = normalize_text(r.get("description"))
            homepage = normalize_text(r.get("homepage"))
            topics = normalize_text("".join(r.get("topics", [])))
            lang = normalize_text(r.get("language"))

            search_blob = name + desc + homepage + topics + lang

            if any(kw in search_blob for kw in normalized_keywords if kw):
                matched_repos.append(r)

        print(f"\nCategory [{cat_name}]: Matched {len(matched_repos)} repos -> {[r['name'] for r in matched_repos]}")

        if matched_repos:
            table_md = generate_table(matched_repos)
            pattern = rf"(<!-- {cat_name}-START -->)(.*?)(<!-- {cat_name}-END -->)"
            
            if re.search(pattern, content, flags=re.DOTALL):
                content = re.sub(pattern, f"\\1\n{table_md}\n\\3", content, flags=re.DOTALL)
                print(f"SUCCESS: Injected {cat_name} table into README.md")
            else:
                print(f"WARNING: Tags <!-- {cat_name}-START --> and <!-- {cat_name}-END --> NOT found in README.md!")

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    update_readme()
