"""Detect substantial exact token copies in first-party source; review semantic reuse separately."""

import argparse
import io
import re
import tokenize
from collections import defaultdict
from pathlib import Path

MIN_TOKENS = 100
MIN_LINES = 12
JS_TOKEN = re.compile(
    r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'
    r"'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|[\w$]+|[^\s]"
)


def tokens(path):
    source = path.read_text()
    if path.suffix == ".py":
        skip = {
            tokenize.COMMENT,
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.ENDMARKER,
            tokenize.ENCODING,
        }
        return [
            (t.string, t.start[0])
            for t in tokenize.generate_tokens(io.StringIO(source).readline)
            if t.type not in skip
        ]
    return [
        (m.group(), source.count("\n", 0, m.start()) + 1)
        for m in JS_TOKEN.finditer(source)
        if not m.group().startswith(("//", "/*"))
    ]


def find_duplicates(roots):
    seen = defaultdict(list)
    findings = {}
    for root in roots:
        if not root.is_dir():
            raise ValueError(f"Missing repository: {root}")
        source = root / "src"
        for path in sorted(source.rglob("*")):
            if path.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                continue
            if path.is_symlink():
                raise ValueError(f"Source symlink requires review: {path}")
            stream = tokens(path)
            for start in range(len(stream) - MIN_TOKENS + 1):
                window = stream[start : start + MIN_TOKENS]
                first, last = window[0][1], window[-1][1]
                if last - first + 1 < MIN_LINES:
                    continue
                key = tuple(token for token, _ in window)
                for other, other_start, other_first, other_last in seen[key]:
                    if other == path and start < other_start + MIN_TOKENS:
                        continue
                    pair = (str(other), str(path))
                    findings.setdefault(pair, (other_first, other_last, first, last))
                seen[key].append((path, start, first, last))
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", type=Path)
    args = parser.parse_args()
    roots = args.roots or [Path(__file__).resolve().parents[1]]
    findings = find_duplicates([root.resolve() for root in roots])
    for (left, right), (a, b, c, d) in findings.items():
        print(f"Repeated source: {left}:{a}-{b} and {right}:{c}-{d}")
    if findings:
        raise SystemExit(
            "DRY check failed: use the existing owner or document a reviewed design change"
        )
    print("DRY token-copy check passed; semantic ownership still requires review")


if __name__ == "__main__":
    main()
