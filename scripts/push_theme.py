#!/usr/bin/env python3
"""Push assets/wikijs/theme.css and body.html to koei.wiki (Administration > Theme > Code Injection).

The repo files are the source of truth; this replaces CSS Override and Body HTML Injection through
the Wiki.js GraphQL API, keeping the other theme settings (theme, icons, dark mode, TOC, Head HTML).
The files' leading header comment is not sent.

The API key is read from the macOS Keychain (service koei-wiki-api-full) and never printed.
Usage: python3 scripts/push_theme.py [--dry-run]
"""

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://koei.wiki/graphql"


def gql(key: str, query: str, variables: dict | None = None) -> dict:
    req = urllib.request.Request(API, json.dumps({"query": query, "variables": variables or {}}).encode(),
                                 {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    out = json.load(urllib.request.urlopen(req, timeout=60))
    if out.get("errors"):
        sys.exit(f"GraphQL error: {out['errors'][0]['message']}")
    return out["data"]


def source(name: str, comment: str) -> str:
    """The file without its leading header comment (comment is a regex for /* */ or <!-- -->)."""
    text = (ROOT / "assets/wikijs" / name).read_text(encoding="utf-8")
    return re.sub(rf"\A\s*{comment}\s*", "", text, count=1, flags=re.S).rstrip() + "\n"


def norm_css(css: str) -> str:
    """Wiki.js reformats the CSS on save (drops comments, last semicolons, selector quotes); compare without those."""
    css = re.sub(r"/\*.*?\*/", "", css or "", flags=re.S)
    css = re.sub(r"\s+", "", css).replace(";}", "}")
    return re.sub(r'="([\w-]+)"\]', r"=\1]", css)  # [src*="INDEX"] is saved as [src*=INDEX]


def main() -> None:
    key = subprocess.run(["security", "find-generic-password", "-s", "koei-wiki-api-full", "-w"],
                         capture_output=True, text=True, check=True).stdout.strip()
    cfg = gql(key, "{ theming { config { theme iconset darkMode tocPosition injectCSS injectHead injectBody } } }")["theming"]["config"]
    css, body = source("theme.css", r"/\*.*?\*/"), source("body.html", r"<!--.*?-->")
    changed = [n for n, same in (("CSS", norm_css(css) == norm_css(cfg["injectCSS"])),
                                  ("Body HTML", body.strip() == (cfg["injectBody"] or "").strip())) if not same]
    if not changed:
        print("live theme already matches the repo")
        return
    print(("would update: " if "--dry-run" in sys.argv else "updating: ") + ", ".join(changed))
    if "--dry-run" in sys.argv:
        return
    res = gql(key, """mutation ($theme: String!, $iconset: String!, $darkMode: Boolean!, $tocPosition: String,
                                $css: String, $head: String, $body: String) {
      theming { setConfig(theme: $theme, iconset: $iconset, darkMode: $darkMode, tocPosition: $tocPosition,
                          injectCSS: $css, injectHead: $head, injectBody: $body) {
        responseResult { succeeded message } } } }""",
              {"theme": cfg["theme"], "iconset": cfg["iconset"], "darkMode": cfg["darkMode"],
               "tocPosition": cfg["tocPosition"], "css": css, "head": cfg["injectHead"], "body": body})
    r = res["theming"]["setConfig"]["responseResult"]
    print("done" if r["succeeded"] else f"failed: {r['message']}")


if __name__ == "__main__":
    main()
