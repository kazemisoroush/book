# Audiobook Generator
A Python CLI that converts text books into multi-voice audiobooks.

# Session Starter
For Claude — fetch at the start of every session:

1. This page (Session Starter)
2. Read and load all packages files word-by-word for code architecture context:
    * [AI Package](../../projects/book/src/ai/README.md)
    * [Audio Package](../../projects/book/src/audio/README.md)
    * [Config Package](../../projects/book/src/config/README.md)
    * [Domain Package](../../projects/book/src/domain/README.md)
    * [Downloader Package](../../projects/book/src/downloader/README.md)
    * [Parser Package](../../projects/book/src/parsers/README.md)
    * [Repository Package](../../projects/book/src/repository/README.md)
    * [Workflows Package](../../projects/book/src/workflows/README.md)

# Review

This file is the rulebook and the review bar. The automated reviewer in
[review.yml](.github/workflows/review.yml) reviews every pull request against
it, and it is the only standard the review judges against. Change the rules by
pull request.

## Review bar

CI already checks formatting, lint, tests, and secrets. A review never repeats a
check CI runs.

A review requests changes only for one of these four, and it quotes the diff for
each blocker:

1. **correctness** — a logic bug, wrong result, race, unhandled error, or a broken edge case.
2. **security** — a leaked secret, missing authn/authz, injection, or unsafe input at a trust boundary.
3. **docs** — a claim in prose or a docstring the code does not support, or a comment that misleads.
4. **abstraction** — an external integration called straight from business logic, an env var or flag read inline instead of through a config layer, a magic literal that should be a named constant, or a one-implementation abstraction that earns nothing.

Anything else is a note, not a blocker. Say it once in the body, then approve.
Taste that no rule here covers is not a reason to hold a pull request.

## Review comments

Every review body follows this format. It is the only source of the shape.

Open with one of three headings, and nothing else:

```md
**🤖 Claude review: approved**
**🤖 Claude review: approved with notes**
**🤖 Claude review: changes requested**
```

Then one sentence saying what was found. Then the findings, if there are any.

Severity has three levels and nothing else. A blocker is 🔴 or 🟠. A note is 🟡,
and a note never blocks a merge.

| Badge | Level | Meaning |
|---|---|---|
| 🔴 | Critical | Breaks the system or exposes it. Merging this causes harm. |
| 🟠 | Major | Wrong or misleading. Merging this leaves a defect behind. |
| 🟡 | Minor | Worth fixing, but safe to merge without it. |

Each finding takes this shape, with `Why.` and `Fix.` each one sentence:

```md
**🟠 Major · abstraction · [`src/ai/client.py:20`](https://github.com/kazemisoroush/book/blob/<sha>/src/ai/client.py#L20)**
The workflow reads `os.environ["OPENAI_API_KEY"]` inline instead of through the config layer.

**Why.** An env var read where it is used cannot be validated or swapped in one place.
**Fix.** Read it in the config package and pass the value in.
```

Close every body with this line:

```md
<sub>Posted by Claude from the review workflow.</sub>
```

Rules for the body:

- Link every file with a full URL against the head commit, as above. A relative
  link resolves against the repository root and lands on a page that does not
  exist, because the comment renders on the pull request page.
- Support each finding with a quote from the diff or the code. A finding with no
  supporting quote is not posted.
- Keep each field to one sentence. A finding that needs a paragraph is really
  several findings, so split it.
- Never leave inline comments. An unresolved review thread blocks the pull
  request, so put every finding in the single review body.

# Code rules

- Always divide tests into 3 parts separated with comments. # Arrange # Act # Assert.
- Remove unnecessary and unused tests on your way of developing new things.
- Never remove an existing inline comment unless asked to, and avoid adding new ones.
- All docstrings are at most 1 short sentence.
- Do not keep history in comments while changing the code.
- Never reference a ticket number in the code. It belongs in the pull request or
  the commit message, not in a comment.
- Variable re-assignment is generally bad practice.
- Every integration lives behind its own abstraction. Any external integration
  (HTTP client, database, queue, third-party SDK, filesystem, cloud service)
  sits behind its own dedicated boundary, never called directly from business logic.
- Always have a config layer for env variables or CLI parameters. Env variables
  and CLI flags are read through the config package, never inline where they are used.
- Prefer named constants or enums over magic strings and numbers.
- Name things explicitly, never abbreviate a word to save characters.
  `configuration` not `cfg`.
- Every linter rule applies to all projects, not one.

# Python

- Every public function has a type hint on its parameters and return.
- Wrap and re-raise with context (`raise X from err`), never swallow an exception silently.
- Keep logic out of the CLI and the API layer; both are thin shells over the packages.
- Prefer `pytest` with plain `assert`, and keep fixtures minimal.
