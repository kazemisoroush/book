# Research Report: Evaluating Agent Harnesses vs Bare Claude Code

**Date**: 2026-04-08
**Query**: How to measure whether custom orchestrator/audit agents outperform bare Claude Code? Is an eval tool the right solution? Should it live in this repo?

---

## Executive Summary

Your team's question is the right one to ask. The honest answer is: **you cannot claim your agent harness is better than bare Claude Code without running controlled comparisons on real tasks.** An eval system is the correct solution, but the word "eval tool" is misleading -- what you need is closer to a **measurement harness** than a product.

The industry consensus (Anthropic, OpenAI, Inspect AI, SWE-bench) is:

1. Eval **infrastructure** should be adopted from existing frameworks (DeepEval, Inspect AI, or lightweight custom scripts)
2. Eval **cases** must be custom-built -- no framework knows what "good" means for your agents
3. Eval cases should **co-locate with the code they test** (same repo), at least initially
4. Start simple: run identical tasks through bare Claude Code vs your agents, measure outcomes

---

## Part 1: Is An Eval Tool The Right Solution?

### Yes, but reframe the question

The team's feedback boils down to: *"prove it works before we invest more."* That's a measurement problem, not a tooling problem. You don't need to build an eval product. You need to:

1. **Define what "better" means** (concrete metrics)
2. **Run controlled comparisons** (same task, agent vs baseline)
3. **Track results over time** (regression detection)

### What "better" actually means for your agents

Your orchestrator and audit agents make specific claims. Each claim maps to a measurable metric:

| Agent Claim | Metric | How to Measure |
|---|---|---|
| TDD is enforced (tests fail before impl) | Test-first compliance rate | Check git history: did test commit precede implementation? |
| Verification gate catches bugs | Phase 3 re-entry rate | Count `[FAIL]` criteria that got fixed before hand-off |
| Role constraints prevent cross-contamination | Role violation count | Did Test Agent ever edit impl? Did Coder Agent edit tests? |
| Bounded retries prevent runaway cost | Retry distribution | Histogram of Coder Agent iterations per task |
| Audit hook catches quality issues | Issues found per task | Count Doc Auditor edits + Test Auditor deletions + dead code removals |
| Overall: better than bare Claude Code | Head-to-head task completion quality | Same task, both approaches, compare code quality + correctness |

### The critical experiment: head-to-head comparison

The single most valuable thing you can do is:

1. Pick 5-10 representative tasks from your spec backlog (mix of simple and complex)
2. Run each task through:
   - **(A)** Bare Claude Code with your CLAUDE.md (no agents, no orchestrator)
   - **(B)** Your full agent fleet (Orchestrator -> Test Agent -> Coder Agent -> Audit Hook)
3. For each outcome, measure:
   - Did the implementation satisfy acceptance criteria? (binary)
   - Test coverage of new code (%)
   - Lint/type check violations remaining (count)
   - Dead code or doc drift introduced (count)
   - Human review time needed before merge (minutes)
   - Total tokens consumed (cost)

This gives you a concrete answer to "is the harness better?" that no amount of architectural reasoning can provide.

---

## Part 2: What Eval Frameworks Exist?

### Tier 1: Adopt for infrastructure

| Framework | Fit for Your Case | Why |
|---|---|---|
| **DeepEval** | Best fit | pytest-style API matches your existing test infra. Free. 30+ metrics. CI/CD integration. `deepeval test run` is analogous to `pytest`. |
| **Inspect AI** (UK AISI) | Good fit, heavier | More mature (5100+ commits). Built-in sandboxing, multi-turn eval, tool-use eval. Free. More setup overhead. |
| **Custom scripts** | Good for starting | Anthropic's own recommendation is to start with simple Python scripts. Their cookbook shows evals as plain functions. No framework needed at first. |

### Tier 2: Use for standardized benchmarks (optional)

| Framework | What It Provides |
|---|---|
| **SWE-bench Verified** | 500 real GitHub issues. Industry standard for coding agent comparison. Proves your harness works on real-world tasks outside your domain. |

### Tier 3: Not recommended for your case

| Framework | Why Not |
|---|---|
| **LangSmith / Braintrust** | Commercial SaaS. Overkill for measuring orchestrator effectiveness. Better suited for production LLM app monitoring. |
| **OpenAI Evals** | OpenAI-centric. Less relevant for Claude-based agents. |
| **AgentBench** | Academic benchmark for general agent capabilities. Not designed for harness comparison. |

### Recommendation: Start with custom scripts, graduate to DeepEval

Phase 1 (now): Write 5-10 eval scripts as plain Python functions. Run them manually. Compare results.

Phase 2 (if evals prove valuable): Migrate to DeepEval for structure, CI integration, and richer metrics.

Phase 3 (if you want external validation): Run SWE-bench Verified to get an industry-comparable score.

---

## Part 3: Should Evals Live In This Repo?

### Yes, for now. Strong yes.

**Arguments for co-location (this repo):**

1. **Atomic changes** -- When you change an agent prompt, the eval that validates it updates in the same PR. Prevents eval rot.
2. **CI integration** -- Your existing pytest + ruff + mypy pipeline can run evals alongside tests.
3. **Developer ergonomics** -- Engineers working on agents can see, modify, and run evals without switching repos.
4. **Refactoring safety** -- If domain types change, co-located evals break immediately.
5. **The testing analogy** -- Unit tests live next to code. Application-specific evals are the same concept.

**When to split into a separate repo (not now):**

- When eval datasets grow large (audio golden files, thousands of test cases)
- When multiple projects share the same eval infrastructure
- When you need different access control (e.g., preventing devs from "teaching to the test")
- When eval CI runs are expensive enough to need separate infrastructure

**Recommended structure in this repo:**

```
src/
  evals/                           # Agent-specific eval cases
    __init__.py
    eval_orchestrator_tdd.py       # Does the TDD loop actually work?
    eval_audit_quality.py          # Do audits catch real issues?
    eval_baseline_comparison.py    # Agent vs bare Claude Code
    fixtures/
      tasks.json                   # Curated task definitions
      expected_outcomes.json       # Golden outputs for comparison
```

This mirrors the `tests/` pattern you already have, but for agent-level evaluation rather than code-level testing.

---

## Part 4: Is This The Right Approach To "The Best AI Harness"?

### The uncomfortable truth

Building evals is necessary but not sufficient. Here's what actually makes an AI harness good:

1. **Evals tell you where you are** -- they measure current performance
2. **Iteration makes you better** -- change prompts, agent boundaries, tool sets, then re-measure
3. **The harness is only as good as your feedback loop** -- if evals run but nobody acts on results, they're wasted

### What the best teams actually do

Based on Anthropic's own SWE-bench work and industry patterns:

1. **Start with tool design** -- Anthropic's key insight from SWE-bench: "much more attention should go into designing tool interfaces for models." Your agent prompts are tool interfaces. The quality of those prompts matters more than the orchestration complexity.

2. **Measure relentlessly** -- Every change to an agent prompt should be followed by a re-run of the eval suite. If the number doesn't go up, the change wasn't an improvement.

3. **Ablation testing** -- Remove one agent at a time and measure. Does removing the Test Agent hurt quality? Does removing the Audit Hook let more drift through? This tells you which agents are carrying their weight.

4. **Keep it simple until the data says otherwise** -- Anthropic's SWE-bench agent was deliberately minimal: a prompt, Bash, and Edit. They outperformed complex scaffolding. Complexity isn't always better. Your evals will tell you whether your 9-agent fleet outperforms a 1-agent setup.

### The real risk: over-engineering the harness

Your team's question hints at this risk. If you can't demonstrate that the orchestrator + audit loop produces measurably better outcomes than a single Claude session with good instructions (your CLAUDE.md), then the complexity is a cost, not a benefit.

The eval system exists to answer one question: **does the added complexity pay for itself?** If the answer is no, the right move is to simplify the harness, not to build more tooling around it.

---

## Part 5: Concrete Next Steps

### Step 1: Define 5-10 eval tasks

Pick real tasks from your spec backlog. Include:
- 2-3 simple tasks (single file change, clear acceptance criteria)
- 2-3 moderate tasks (multi-file, some ambiguity)
- 2-3 complex tasks (cross-module, architectural decisions)

### Step 2: Run baseline comparison

For each task:
- Run with bare Claude Code + CLAUDE.md (no agents)
- Run with full agent fleet (Orchestrator -> Test Agent -> Coder Agent -> Audit Hook)
- Record: correctness, test coverage, lint/type violations, tokens consumed, human review time

### Step 3: Analyze results

- If agents consistently outperform baseline: document the margins and keep investing
- If results are mixed: identify which agents add value and which don't
- If baseline wins: simplify the harness

### Step 4: Automate the comparison

Once you know what to measure, wrap it in scripts that can run in CI. This is your eval system. It doesn't need to be a product -- it's a measurement harness.

### Step 5: Iterate

Change agent prompts, re-run evals, track improvement over time. This is the actual work of building a good harness.

---

## Sources

| Source | Credibility | Key Insight |
|---|---|---|
| Anthropic platform docs (develop-tests) | Authoritative | Custom evals recommended; LLM-as-judge + code grading patterns |
| Anthropic SWE-bench blog | Authoritative | Minimal harness outperformed complex scaffolding; tool design matters most |
| Anthropic cookbook (building_evals.ipynb) | Authoritative | Evals as simple Python scripts; no special framework needed |
| DeepEval (deepeval.com) | High | pytest-style eval framework; 30+ metrics; CI/CD integration |
| Inspect AI (UK AISI) | High | 5100+ commits; 100+ built-in evals; framework/eval split pattern |
| SWE-bench (Princeton NLP) | High | Industry standard coding agent benchmark; dynamic data fetching |
| Hamel Husain (hamel.dev) | High (practitioner) | "Least friction in your tech stack" principle for evals |

---

## Confidence Levels

| Finding | Confidence |
|---|---|
| You need evals before claiming the harness is better | **High** -- this is universally agreed |
| Start with co-located evals in this repo | **High** -- strong consensus across sources |
| DeepEval is the best fit for your pytest-based workflow | **Medium-High** -- good fit but Inspect AI is also viable |
| Head-to-head comparison is the most valuable first experiment | **High** -- directly answers the team's question |
| Custom scripts before frameworks | **Medium** -- depends on team preference; some prefer structure from day 1 |
| The harness may be over-engineered | **Medium** -- can only be confirmed by running the comparison |
