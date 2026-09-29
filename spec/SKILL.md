---
name: spec
description: Pin down what will be built and what must be true when it is done, BEFORE building. Use for any task bigger than a quick fix - a new feature, a redesign, a delivery to a client, multi-step work, anything over ~30 minutes or touching several files or services. Produces a spec with measurable acceptance criteria, which is then the only basis for saying "done".
---

# spec

Most wasted work is redone work, and redone work usually starts with an unclear goal. Five minutes here is cheaper than five attempts later.

## When to use it, and when not

Use it when at least one is true:
- the job takes more than ~30 minutes
- it touches several files, services or machines
- it goes to a client or to production
- it is hard to undo
- the request was one sentence and can be read more than one way

Skip it for one-line fixes, plain questions, and when the person says "just do it". Inventing a spec for a three-line fix kills the habit.

## Steps

1. **Read first.** Never ask what you can find out yourself from the code, the docs or earlier notes.
2. **Ask, in one message, at most five numbered questions, each with your own proposal as the default:**
   ```
   1. <question>  — my proposal: <X>
   2. <question>  — my proposal: <Y>
   ```
   Then a short "yes" means "go with the proposals".
3. **Write the spec:** `python3 spec.py new "<title>"`, then fill in every section. Criteria must be true or false. Write how each one is measured when you write it. "Should feel premium" is not a criterion; it goes under DIRECTION.
4. **Show it and wait for a yes.** Do not build before.
5. **Build.** If a criterion turns out to be wrong, change it in the file and say so. Quietly reinterpreting a criterion is the same as not having one.
6. **Verify:** `python3 spec.py verify <spec>`. It fails on missing, placeholder, too-short evidence, or evidence that only repeats the measuring method. Evidence is what you ran and what came out: the command and its output, the number, the test result.
7. **Close:** `python3 spec.py close <spec>`, then tell the person what was built, what was measured and what was left out.

Never say "done" before `verify` passes. If a criterion cannot be met, say so plainly instead of rounding it off.
