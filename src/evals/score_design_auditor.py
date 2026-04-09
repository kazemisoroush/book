"""Scorer for the Design Auditor eval.

The Design Auditor files each finding as a td-XXX spec in docs/specs/.
This scorer checks whether the generated specs correctly identify planted
smells.

Usage:
    python -m src.evals.score_design_auditor setup
    # run the Design Auditor agent targeting the planted file
    python -m src.evals.score_design_auditor score
    python -m src.evals.score_design_auditor cleanup
"""
import re
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
MODULE_SRC = FIXTURE_DIR / "planted_design_smells.py"
MODULE_DST = Path(__file__).parent.parent / "domain" / "planted_design_smells_eval.py"
SPECS_DIR = Path(__file__).parent.parent.parent / "docs" / "specs"

# Violations the agent should detect.
# (category, description, keywords_any_of — at least one must appear in a spec)
EXPECTED_VIOLATIONS = [
    (
        "feature-envy",
        "find_best_voice reaches into VoiceProfile internals instead of delegating",
        ["feature.?envy", "reach.*internal", "belong.*on.*voice", "delegat"],
    ),
    (
        "god-function",
        "process_chapter does parse + validate + assign + format + persist",
        ["god.?func", "too many", "multiple.*responsib", "single.?resp", "srp",
         "parse.*validate.*persist", "five.*phase", "many.*things"],
    ),
    (
        "primitive-obsession",
        "process_chapter returns dict[str, Any] instead of a typed model",
        ["primitive.?obsess", r"dict\[", "raw.?dict", "typed.?model", "dataclass"],
    ),
    (
        "leaking-abstraction",
        "process_chapter validates segment length/emptiness — belongs in AudioSegment",
        ["leak", "abstraction", "validat.*belongs", "belongs.*lower",
         "segment.*length", "length.*check"],
    ),
    (
        "dependency-inversion",
        "Domain module imports os/json and does file I/O directly",
        ["dependency.?invers", "import.*os", "import.*json", "infrastructure",
         "domain.*i.?o", "file.*i.?o", "layer.*violat"],
    ),
    (
        "open-closed",
        "select_output_format uses if/elif chain on mode string",
        ["open.?closed", "elif.*chain", "if.*chain", "extensi", "mode.*string",
         "dispatch", "grow"],
    ),
]

# Things that should NOT be flagged
EXPECTED_CLEAN = [
    ("VoiceProfile", "Simple dataclass — no violation"),
    ("AudioSegment", "Simple dataclass — no violation"),
    ("count_words", "Small focused helper — no violation"),
    ("estimate_duration", "Pure function — no violation"),
]


def _strip_eval_metadata(source: str) -> str:
    """Remove eval tags so the planted file looks like ordinary code."""
    result = re.sub(
        r'"""Planted design smells.*?"""',
        '"""Helpers for chapter processing and voice assignment."""',
        source,
        count=1,
        flags=re.DOTALL,
    )
    result = re.sub(r'\s*#\s*SMELL:\S+.*$', '', result, flags=re.MULTILINE)
    result = re.sub(r'\s*#\s*CLEAN.*$', '', result, flags=re.MULTILINE)
    return result


def _find_generated_specs() -> list[Path]:
    """Find td-*.md specs that reference the planted eval module."""
    specs = []
    for path in sorted(SPECS_DIR.glob("td-*.md")):
        content = path.read_text().lower()
        if "planted_design_smells_eval" in content:
            specs.append(path)
    return specs


def _concat_specs(specs: list[Path]) -> str:
    """Read and concatenate all generated spec files into one string."""
    parts = []
    for path in specs:
        parts.append(path.read_text())
    return "\n\n".join(parts).lower()


def setup() -> None:
    """Plant a module with design smells into domain/."""
    cleaned = _strip_eval_metadata(MODULE_SRC.read_text())
    MODULE_DST.write_text(cleaned)
    print(f"Planted module at {MODULE_DST}")
    print()
    print("Now run the Design Auditor agent targeting this file:")
    print(f"  Audit {MODULE_DST}")
    print()
    print("The agent will create td-XXX specs in docs/specs/.")
    print("Then run:")
    print("  python -m src.evals.score_design_auditor score")


def score() -> None:
    """Score the Design Auditor's specs against expected violations."""
    specs = _find_generated_specs()
    if not specs:
        print("ERROR: No td-*.md specs found referencing planted_design_smells_eval")
        print("Run the Design Auditor agent first, then try again.")
        sys.exit(1)

    print(f"Found {len(specs)} spec(s) referencing the planted module:")
    for s in specs:
        print(f"  {s.name}")
    print()

    report = _concat_specs(specs)

    # --- Recall: did the specs mention each planted smell? ---
    detected = []
    missed = []

    for category, description, keywords in EXPECTED_VIOLATIONS:
        found = any(re.search(kw, report) for kw in keywords)
        if found:
            detected.append((category, description))
        else:
            missed.append((category, description))

    # --- Precision: did it avoid flagging clean code? ---
    false_positives = []
    correctly_clean = []

    for name, description in EXPECTED_CLEAN:
        name_lower = name.lower()
        # A clean item is falsely flagged only if a spec title names it as the
        # *problem* — e.g. "Fix VoiceProfile" or "VoiceProfile violates SRP".
        # Titles like "Move logic TO VoiceProfile" are fine — the class is the
        # fix destination, not the violation subject.  We check for the name
        # appearing in a title WITHOUT "move...to" or "into" framing.
        title_flagged = False
        for m in re.finditer(
            r'^#\s+td-\d+\s*—\s*(.+)$', report, re.MULTILINE,
        ):
            title = m.group(1)
            if name_lower not in title:
                continue
            # If the title says "move X to <name>" or "into <name>", it's fine
            if re.search(rf'(?:move|extract|into|to)\s+.*{name_lower}', title):
                continue
            title_flagged = True
            break
        flagged = title_flagged
        if flagged:
            false_positives.append((name, description))
        else:
            correctly_clean.append((name, description))

    # --- Structure: do the specs follow the td- template? ---
    has_goal = bool(re.search(r'##\s*goal', report))
    has_problem = bool(re.search(r'##\s*problem', report))
    has_acceptance = bool(re.search(r'##\s*acceptance criteria', report))
    has_concept = bool(re.search(r'##\s*concept', report))

    structure_checks = [
        ("Goal section", has_goal),
        ("Problem section", has_problem),
        ("Concept section", has_concept),
        ("Acceptance criteria section", has_acceptance),
    ]

    total_violations = len(EXPECTED_VIOLATIONS)
    total_clean = len(EXPECTED_CLEAN)
    total_structure = len(structure_checks)

    print("=" * 60)
    print("DESIGN AUDITOR EVAL RESULTS")
    print("=" * 60)

    print(f"\nRecall — violation detection: {len(detected)}/{total_violations}")
    for cat, desc in sorted(detected):
        print(f"  PASS  {cat}: {desc}")
    for cat, desc in sorted(missed):
        print(f"  FAIL  {cat}: {desc}")

    print(f"\nPrecision — clean code not flagged: {len(correctly_clean)}/{total_clean}")
    for name, desc in sorted(correctly_clean):
        print(f"  PASS  {name}: {desc}")
    for name, desc in sorted(false_positives):
        print(f"  FAIL  {name}: {desc}")

    structure_passed = sum(1 for _, ok in structure_checks if ok)
    print(f"\nStructure — spec format: {structure_passed}/{total_structure}")
    for label, ok in structure_checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")

    recall = len(detected) / total_violations if total_violations else 0
    precision = len(correctly_clean) / total_clean if total_clean else 0
    structure_score = structure_passed / total_structure if total_structure else 0

    print(f"\nRecall:    {recall:.0%} ({len(detected)}/{total_violations} violations detected)")
    print(f"Precision: {precision:.0%} ({len(correctly_clean)}/{total_clean} clean symbols not flagged)")
    print(f"Structure: {structure_score:.0%} ({structure_passed}/{total_structure} format checks)")

    overall = recall == 1.0 and precision == 1.0 and structure_score == 1.0
    print(f"Score:     {'PASS' if overall else 'FAIL'}")


def cleanup() -> None:
    """Remove planted file and any generated specs referencing it."""
    removed = []

    if MODULE_DST.exists():
        MODULE_DST.unlink()
        removed.append(str(MODULE_DST))

    for spec in _find_generated_specs():
        spec.unlink()
        removed.append(str(spec))

    if removed:
        for r in removed:
            print(f"Removed {r}")
    else:
        print("Nothing to clean up.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "setup":
        setup()
    elif cmd == "score":
        score()
    elif cmd == "cleanup":
        cleanup()
    else:
        print("Usage: python -m src.evals.score_design_auditor [setup|score|cleanup]")
