# The method

This is how the post [Orca, OpenRig and Herdr, and What None of Them Do](https://ry-ops.dev/posts/2026-10-27-orca-openrig-herdr-what-none-of-them-do/) was made. `receipts` turns the parts that can be checked into commands.

## 1. Decide what a reader needs to know, before testing

Write the questions down first, as rows of a capability map. If you only write rows after testing, you end up reporting what was easy to test instead of what matters.

## 2. Test for real, in a lab

Install the tools and run them on a small, disposable repo with a real task. In the post, that was a `slugify()` function with a failing test. One tool's output fed the next tool's task. The OpenRig reviewer's two follow-ups became the two parallel Orca tasks. That chain made the comparison fair, and it also produced the most useful finding: two correct branches that still conflicted at merge.

## 3. Keep the evidence word for word

Save terminal output as it appeared. Give every record a kind and a one-sentence description of what it shows. The kinds are a live capture, an agent-session transcript, a screen read-out, reformatted tool output, a screenshot or a note. Mark anything your own script added, like formatting or timing, as yours. Replace local paths with stand-ins such as `~/ry-ops`, and say in the record that you did. That's the only edit evidence ever gets.

## 4. Give every claim one of three labels

| Label | Means | Must cite |
|---|---|---|
| Tested | I ran it and saw it | Evidence ids, plus an excerpt that appears in them word for word |
| Documented | The project says so; I didn't test it | A URL or CLI help, with version |
| Not found | I looked and it isn't there | Where I looked |

A "gap" is a row where every subject is *not found*. It's the strongest claim in the write-up, so the tool refuses a gap row that has anything else in it.

## 5. Check every quote against its source

Fetch the page and confirm the exact words are on it. Curly quotes, dashes and spacing are normalized; wording is not. Bot-check pages are reported as blocked, never as found.

## 6. Build the figures from the evidence

The figures read only from the generated data, so a figure can't say more than the ledger does. Every figure has a text fallback that says the same thing.

## 7. Say who tested, what, when, and what you didn't test

The post opens with a "how this was tested" box and ends with a versions footer. Both are generated. It names the tester, even when that's an AI agent, and lists what wasn't tested.

## What the tool can't check

`receipts` can prove a quote exists, an excerpt is in the evidence, and every claim has a label. It can't prove your prose matches your ledger, or that you labeled honestly in the first place. That part is still on the writer.
