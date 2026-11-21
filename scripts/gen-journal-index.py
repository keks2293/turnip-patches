#!/usr/bin/env python3
"""Regenerate the journal index (docs/analysis.md) and the machine manifest
(docs/journal/manifest.json) from the entry files in docs/journal/.

Why a generator: the index is the first file an agent reads, and a hand-maintained
index goes stale exactly in the columns that matter (status, artifacts). Everything
here is read out of the entry files; the only hand-written input is STATUS below,
because "closed" is a judgement, not a parse.

Run after adding or editing an entry:
    python3 scripts/gen-journal-index.py
"""
import json
import os
import re
import sys

JOURNAL = "docs/journal"
INDEX = "docs/analysis.md"
MANIFEST = os.path.join(JOURNAL, "manifest.json")

# entry id -> state of the branch it investigated. Vocabulary is deliberately small:
#   shipped     - a patch from this entry is in the release
#   closed      - the branch is closed, no patch (a verdict, usually an ADR)
#   open        - the next measurement is queued in docs/plan-next-checks.md
#   reference   - the entry is used as a reference, it is not a closed question
#   operational - procedure/env material, belongs to a how-to page eventually
#   corrected   - the entry's first conclusion was later corrected; read the update
STATUS = {
    "1": "shipped", "2": "shipped", "2.1": "reference", "3": "shipped", "4": "shipped",
    "5": "reference", "6": "reference", "7": "operational", "8": "operational",
    "9": "operational", "10": "operational", "11": "operational", "12": "operational",
    "13": "closed", "14": "closed", "15": "closed", "16": "closed", "17": "closed",
    "18": "shipped", "19": "operational", "20": "corrected", "21": "shipped",
    "21.10": "shipped", "21.11": "shipped", "21.12": "shipped",
    "22": "closed", "23": "closed", "24": "closed", "25": "reference", "26": "closed",
    "27": "closed", "28": "open", "29": "reference", "30": "closed", "31": "open",
    "32": "open", "33": "open", "34": "open", "35": "open", "36": "closed",
}
# where the verdict lives when the entry is not the owning document
DECISIONS = {
    "1": "ADR-0002, ADR-0011", "2": "ADR-0002", "2.1": "ADR-0001, ADR-0003",
    "3": "ADR-0011", "4": "ADR-0002", "13": "ADR-0008", "14": "ADR-0008",
    "15": "ADR-0008", "16": "ADR-0003", "17": "ADR-0008", "18": "ADR-0003",
    "20": "ADR-0005", "21": "ADR-0003", "21.10": "ADR-0005", "21.11": "ADR-0005",
    "21.12": "ADR-0006", "22": "ADR-0007", "23": "ADR-0010", "24": "ADR-0001",
    "26": "ADR-0001", "27": "ADR-0006", "28": "ADR-0004, ADR-0007",
}

# what the entry asks, when the heading itself is not a question (entries 1-19 were
# written as report headings, not as questions). Used only for the index column; the
# verbatim heading stays in the manifest as `title`.
QUESTION = {
    "1": "what the game reports, and what the driver exposes",
    "2": "why 12_0 is refused: which property chain ends in TiledResourcesTier = TIER_1",
    "2.1": "which different things disable UBWC, and which of them is the mutable-list gate",
    "3": "is 12_0 reachable without forcing anything",
    "4": "what changes when the sparse-residency gate is lifted",
    "5": "what is worth reporting upstream about the gate",
    "6": "how to reproduce the whole result from a clean prefix",
    "7": "how to swap the driver on the device without reflashing",
    "8": "how to run the game and read its logs",
    "9": "why the patched driver failed vkCreateInstance",
    "10": "what actually caused that rejection (prefix=/out/usr)",
    "11": "which benchmark is worth measuring with on this device",
    "12": "why a timed-out run left the game alive, and what that did to the numbers",
    "13": "does fps depend on anything in the driver",
    "14": "does the driver under-use the A750/A830 generation",
    "15": "what the device properties give or cost in vkmark and in RE4",
    "16": "can gen2 tile and compress a mixed-order {BGRA8, RGBA8} list",
    "17": "how much memory RE4 holds, and in what",
    "18": "does NV12 + MUTABLE have to lose the tiling",
    "19": "why the build image produced a driver that would not load",
    "34": "which perf-relevant options exist outside TU_FORCE_PROPS, and which of them a740 has never run with",
    "35": "does this stack ever ask for a fragment density map or a shading-rate attachment, and what does the driver do with one",
    "36": "does exp-21 make the same tiling decision as the shipped 0014 on the game's own creates",
}

DECISION_DIR = "docs/decisions"


def load_adrs():
    """ADR id -> (title, first sentence of `## Decision`), quoted verbatim.

    The index quotes the owner of the verdict instead of paraphrasing it: a summary
    written by hand is exactly where this repository has overstated a result before.
    """
    adrs = {}
    if not os.path.isdir(DECISION_DIR):
        return adrs
    for fname in sorted(os.listdir(DECISION_DIR)):
        m = re.match(r"ADR-(\d{4})-.+\.md$", fname)
        if not m:
            continue
        text = open(os.path.join(DECISION_DIR, fname)).read()
        title = next((l[2:].strip() for l in text.split("\n") if l.startswith("# ")), fname)
        lines = text.split("\n")
        try:
            i = next(k for k, l in enumerate(lines) if l.strip() == "## Decision")
        except StopIteration:
            continue
        para = []
        for l in lines[i + 1:]:
            if l.strip() == "" and para:
                break
            if l.strip().startswith("#"):
                break
            if l.strip():
                para.append(l.strip())
        adrs[m.group(1)] = (title, " ".join(para))
    return adrs


def quote(text, limit=200):
    """A verbatim prefix of the owner's sentence - never a rewrite. The ellipsis says
    the quote was cut, so nobody mistakes the cut for the end of the verdict."""
    text = re.sub(r"`|\*\*", "", text).strip()
    return text[:limit] + ("\u2026" if len(text) > limit else "")


ART_RE = re.compile(
    r"(?:results|patches|tests|scripts|experiments|tools|docs|build)/"
    r"[A-Za-z0-9_.{},*~/-]+")
DATE_RE = re.compile(r"(\d{1,2}\.\d{1,2}(?:\.\d{4})?"
                     r"(?:\s*-\s*\d{1,2}\.\d{1,2}(?:\.\d{4})?)?)")


def sort_key(num):
    return tuple(int(p) for p in num.split("."))


def parse(path, fname):
    text = open(path).read()
    lines = text.split("\n")
    h1 = next((l[2:].strip() for l in lines if l.startswith("# ")), fname)
    m = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$", h1)
    num, title = (m.group(1), m.group(2)) if m else ("", h1)
    body = "\n".join(lines)
    tail = re.search(r"\(([^()]*)\)\s*$", h1)
    dm = DATE_RE.search(tail.group(1)) if tail else None
    date = dm.group(1) if dm else ""
    # artifacts: real paths mentioned in the entry, minus pointers to the docs tree
    arts = []
    for a in ART_RE.findall(body):
        a = a.rstrip(".,;:")
        if a.startswith("docs/") or a in arts or a.endswith("/"):
            continue
        if "*" in a and not a.endswith(".log"):
            continue
        arts.append(a)
    verdict = ""
    for l in body.split("\n"):
        s = l.strip().lstrip("*>- ").strip()
        if re.match(r"^\*{0,2}(Verdict|Verdicts|Conclusion|Conclusions|Summary|Outcome|"
                    r"Result|Bottom line)", s, re.I):
            s = re.sub(r"\*+", "", s)
            s = re.sub(r"^\s*(Verdicts?|Conclusions?|Summary|Outcome|Result|"
                       r"Bottom line)\s*[:\-]?\s*", "", s, flags=re.I)
            verdict = s[:200] + ("…" if len(s) > 200 else "")
            break
    return {
        "id": num,
        "title": title,
        "question": QUESTION.get(num, title),
        "file": f"journal/{fname}",
        "date": date,
        "status": STATUS.get(num, "unset"),
        "decision": DECISIONS.get(num, ""),
        "verdict_first_line": verdict,
        "artifacts": arts[:12],
        "lines": len(lines),
        "headings": [l for l in lines if l.startswith("## ")],
    }


def main():
    if not os.path.isdir(JOURNAL):
        sys.exit(f"{JOURNAL} not found - run from the repository root")
    entries = []
    for fname in sorted(os.listdir(JOURNAL)):
        if not fname.endswith(".md") or fname == "README.md":
            continue
        entries.append(parse(os.path.join(JOURNAL, fname), fname))
    entries.sort(key=lambda e: sort_key(e["id"]))
    adrs = load_adrs()

    unknown = [e["id"] for e in entries if e["status"] == "unset"]
    if unknown:
        print("WARNING: no STATUS for entries: " + ", ".join(unknown), file=sys.stderr)

    for e in entries:
        m = re.match(r"ADR-(\d{4})", e["decision"]) if e["decision"] else None
        if m and m.group(1) in adrs:
            e["verdict_quote"] = quote(adrs[m.group(1)][1], 400)
            e["verdict_source"] = f"ADR-{m.group(1)}"
        elif e["verdict_first_line"]:
            e["verdict_quote"] = quote(e["verdict_first_line"], 400)
            e["verdict_source"] = f"journal {e['id']}"
        else:
            e["verdict_quote"] = ""
            e["verdict_source"] = ""
    json.dump({"entries": entries}, open(MANIFEST, "w"), indent=1, ensure_ascii=False)

    rows = []
    for e in entries:
        arts = ", ".join(f"`{a}`" for a in e["artifacts"][:3]) or "-"
        if len(e["artifacts"]) > 3:
            arts += f" (+{len(e['artifacts']) - 3})"
        asked = e["question"].replace("|", chr(92) + "|")
        vquote, owner = "", "-"
        first_adr = re.match(r"ADR-(\d{4})", e["decision"]) if e["decision"] else None
        if first_adr and first_adr.group(1) in adrs:
            _, decision_line = adrs[first_adr.group(1)]
            vquote = quote(decision_line, 190)
            owner = f"[{e['decision']}](decisions/README.md)"
        elif e["verdict_first_line"]:
            vquote = quote(e["verdict_first_line"], 190)
            owner = f"[{e['file'].split('/')[-1]}]({e['file']})"
        elif e["decision"]:
            vquote = quote(e["title"], 190)
            owner = f"[{e['decision']}](decisions/README.md)"
        q = vquote.replace("|", chr(92) + "|") or "-"
        rows.append(f"| [{e['id']}]({e['file']}) | {e['status']} | {e['date'] or '-'} "
                    f"| {asked} | {owner} | {q} | {arts} |")

    out = INDEX_HEADER.replace("{{ROWS}}", "\n".join(rows))
    total = sum(e["lines"] for e in entries)
    out = out.replace("{{N}}", str(len(entries))).replace("{{LINES}}", str(total))
    open(INDEX, "w").write(out)
    print(f"{len(entries)} entries, {total} lines -> {INDEX}, {MANIFEST}")


INDEX_HEADER = """# The journal - index

{{N}} entries, {{LINES}} lines of journal, one file per experiment in
[`docs/journal/`](journal/). This page owns no measurement: it exists so that opening
the wrong file is unnecessary. Generated by `scripts/gen-journal-index.py` - never edit
it by hand.

## How to read this as an agent

1. Find the entry by the `what was asked` column, or search instead of reading:
   ```sh
   grep -ril "metadata plane" docs/journal/          # full text of every entry
   grep -n "pipelineCache" docs/journal/manifest.json # index as JSON, with the entry id
   ```
   `manifest.json` carries one object per entry: id, file, title, question, status,
   date, verdict_first_line, artifacts, headings, lines.
2. `status` tells you whether to read at all. `shipped` and `closed` mean the question is
   settled - the owner of the verdict is the ADR in the next column, the entry is the
   evidence behind it. `open` means a measurement is queued in
   [`docs/plan-next-checks.md`](plan-next-checks.md). `corrected` means the entry's first
   conclusion was later wrong: read its dated update before quoting a number.
   `reference` and `operational` are material you consult while working.
3. Cite as `journal NN` or `journal NN.M`. The number is the heading number inside the
   file and the file name starts with it, so `journal 21.10` opens
   `docs/journal/21-10-*.md` and looks for heading 21.10 without searching. Numbers are
   never renumbered and never reused, which is why references written months ago still
   resolve - including the ones written as `analysis` SSNN before the journal was split
   into files on 20.11 (the old document of that name is this index).
4. Do not copy a number out of an entry into another document. Write `journal NN` instead
   (rules: [`../AGENTS.md`](../AGENTS.md)).
5. A `date` is taken from the entry heading; entries 7-19 carry none there, the
   chronology of the whole work is in [`docs/release.md`](release.md) (History).

| journal | status | date | what was asked | owner of the verdict | the verdict, in the owner's own words | main artifacts |
|---|---|---|---|---|---|---|
{{ROWS}}

## Layout around the journal

| document | what it owns |
|---|---|
| [`docs/journal/`](journal/) | one entry per experiment: question, method, command, numbers, verdict, artifacts, and "what this does not show"; append-only, corrections go inside as dated paragraphs |
| [`docs/decisions/`](decisions/) | a verdict that closes a branch (ADR, immutable, superseded rather than edited) |
| [`docs/streams/`](streams/) | where a direction stands now, with pointers and no new numbers |
| [`docs/release.md`](release.md) | shipped code, hashes, reference builds, versions, the release procedure, chronology |
| [`docs/artifacts.md`](artifacts.md) | inventory: tools, scripts, logs, what each proves |
| [`docs/howto-measure.md`](howto-measure.md) | protocols: the fps window, correctness runs, run hygiene |
| [`docs/plan-next-checks.md`](plan-next-checks.md) | the queue, the open questions, the pitfalls |
| [`docs/archive/`](archive/) | frozen reports, including the 19.11 consolidated report this structure replaced; never cited as evidence |

Entries 7-12 and 19 are operational material - procedure and environment, kept in the
journal as dated investigations. A distilled how-to page over them is queued in
`docs/plan-next-checks.md`.
""".replace("SS", "\u00a7")


if __name__ == "__main__":
    main()
