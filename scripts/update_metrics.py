"""Update public repository totals without replacing assets on collection failure."""
from pathlib import Path
from urllib.request import Request, urlopen
from collections import Counter
import json, os, html, tempfile

ROOT = Path(__file__).resolve().parents[1]
OWNER = "KauannOliver"

def collect(fetch):
    repos = []
    page = 1
    while True:
        batch = fetch(f"https://api.github.com/users/{OWNER}/repos?type=owner&per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ValueError("Expected a public repository list")
        for repo in batch:
            if not isinstance(repo, dict) or repo.get("owner", {}).get("login", "").lower() != OWNER.lower():
                raise ValueError("Unexpected repository owner")
            if repo.get("private") or repo.get("fork"):
                continue
            for field in ("stargazers_count", "forks_count"):
                if not isinstance(repo.get(field), int) or repo[field] < 0:
                    raise ValueError("Invalid repository metric")
            repos.append(repo)
        if len(batch) < 100:
            break
        page += 1
        if page > 100:
            raise ValueError("Pagination limit exceeded")
    if not repos:
        raise ValueError("Refusing to overwrite valid totals with an empty collection")
    if len({repo["name"] for repo in repos}) != len(repos):
        raise ValueError("Duplicate repositories")
    languages = Counter(repo["language"] for repo in repos if repo.get("language"))
    return {"owner": OWNER, "repositories": len(repos), "stars": sum(r["stargazers_count"] for r in repos),
            "forks": sum(r["forks_count"] for r in repos), "primary_languages": dict(sorted(languages.items())),
            "methodology": "Public, owned, non-fork repositories; language is each repository's primary language."}

def render(metrics):
    values = [("PUBLIC REPOSITORIES", metrics["repositories"]), ("STARS", metrics["stars"]),
              ("FORKS", metrics["forks"]), ("PRIMARY LANGUAGES", len(metrics["primary_languages"]))]
    cells = "".join(f'<text x="{30+i*260}" y="58" font-family="sans-serif" font-size="16" fill="#AAB3C5">{label}</text>'
                    f'<text x="{30+i*260}" y="115" font-family="monospace" font-size="42" fill="#00D4FF">{value}</text>'
                    for i, (label, value) in enumerate(values))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="150" viewBox="0 0 1100 150" role="img" aria-labelledby="title">'
            '<title id="title">Public GitHub repository metrics</title><rect width="1100" height="150" rx="18" fill="#0B1026"/>'+cells+'</svg>')

def request_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "KauannOliver-public-metrics"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return json.load(response)

def update(fetch=request_json, root=ROOT):
    # Collection and rendering must both succeed before any existing asset is touched.
    metrics = collect(fetch)
    payloads = {"metrics.json": json.dumps(metrics, indent=2, sort_keys=True)+"\n", "overview.svg": render(metrics)+"\n"}
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    prepared = []
    try:
        for name, content in payloads.items():
            target = assets / name
            if target.exists() and target.read_text(encoding="utf-8") == content:
                continue
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=assets, delete=False) as handle:
                handle.write(content)
                prepared.append((Path(handle.name), target))
        for temp, target in prepared:
            os.replace(temp, target)
    finally:
        for temp, _ in prepared:
            temp.unlink(missing_ok=True)
    return metrics

if __name__ == "__main__":
    try:
        result = update()
    except Exception as exc:
        raise SystemExit(f"Metrics collection failed ({type(exc).__name__}); previous valid assets retained.")
    print(f"Collected {result['repositories']} public repositories.")
