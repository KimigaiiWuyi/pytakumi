from pathlib import Path
import re
import difflib

p2 = Path(r"C:\Users\44483\Desktop\stamina_card.html_test2.html")
p3 = Path(r"C:\Users\44483\Desktop\stamina_card.html_test3.html")
h2 = p2.read_text(encoding="utf-8", errors="replace")
h3 = p3.read_text(encoding="utf-8", errors="replace")


def styles(h: str) -> str:
    m = re.findall(r"<style[^>]*>(.*?)</style>", h, flags=re.I | re.S)
    return m[0] if m else ""


def body_clean(h: str) -> str:
    m = re.search(r"<body[^>]*>(.*?)</body>", h, flags=re.I | re.S)
    b = m.group(1) if m else h
    return re.sub(r"data:image/[^\"']+", "DATAURL", b)


s2, s3 = styles(h2), styles(h3)
print("=== STYLE DIFF ===")
for line in difflib.unified_diff(
    s2.splitlines(), s3.splitlines(), fromfile="test2.css", tofile="test3.css", lineterm="", n=2
):
    print(line[:240])

print("\n=== BODY DIFF (data stripped) ===")
for line in difflib.unified_diff(
    body_clean(h2).splitlines(),
    body_clean(h3).splitlines(),
    fromfile="test2.html",
    tofile="test3.html",
    lineterm="",
    n=1,
):
    print(line[:240])

# Extract footer-related CSS blocks
for name, css in [("test2", s2), ("test3", s3)]:
    print(f"\n=== {name} footer-ish rules ===")
    for m in re.finditer(
        r"([.#][\w-]*(?:footer|bottom|dock|bar|user|profile|stat|wave|icon)[\w-]*)\s*\{[^}]+\}",
        css,
        flags=re.I,
    ):
        print(m.group(0)[:300])
        print("---")
