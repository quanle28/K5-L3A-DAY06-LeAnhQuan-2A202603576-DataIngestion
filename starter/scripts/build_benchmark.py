"""Author-defined benchmark, evidence resolved against corpus BEFORE retrieval."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "starter"))
from src.evaluation import canonical
from src.ingestion import load_pages

# Each quote below is selected from the corpus; no retrieval results are used.
SPECS = [
("introduction", "What type does ordinary division return, and which operators give floor division and the remainder?",
 "Division (/) always returns a float.", "the remainder you can use %::", "A float; // for floor division, % for the remainder.", "direct", False),
("introduction", "Can I replace a character of a Python string by assigning to its index?",
 "Python strings cannot be changed", "assigning to an indexed position in the string results in an error::", "No. Strings are immutable; indexed assignment raises an error.", "paraphrase", False),
("introduction", "Which negative index selects the last character, and why is it not negative zero?",
 "Indices may also be negative numbers", "negative indices start from -1.", "Use -1; -0 is the same as 0.", "condition", False),
("controlflow", "If loops are nested, which loop does a break statement exit?",
 "The break statement breaks out", "for or while loop.", "The innermost enclosing for or while loop.", "direct", False),
("controlflow", "In the control-flow chapter, does a loop's else clause run after a break terminates the loop?",
 "In either kind of loop", "if the loop was terminated by a break.", "No; the else clause is not executed after break.", "condition", True),
("controlflow", "Why can a list used as a function's default argument keep values between calls?",
 "**Important warning:** The default value is evaluated only once.", "arguments passed to it on subsequent calls::", "The default is evaluated once, so a mutable default is shared by later calls.", "paraphrase", False),
("controlflow", "What value comes back if a Python function reaches the end without an explicit return?",
 "* The return statement returns", "the end of a function also returns None.", "None.", "direct", False),
("datastructures", "In the data-structures chapter, how can I append a single item at the end of a list?",
 ".. method:: list.append(x)", "Equivalent to a[len(a):] = [x].", "Call list.append(x).", "direct", True),
("datastructures", "What does a.pop() remove and return when no index is supplied?",
 "Remove the item at the given position", "a.pop() removes and returns the last item in the list.", "The last item in the list.", "condition", False),
("datastructures", "Which container is designed for efficient queue insertion and removal at both ends?",
 "To implement a queue, use collections.deque", "have fast appends and pops from both ends.", "collections.deque.", "paraphrase", False),
("datastructures", "Why can't a list be a dictionary key?",
 "Unlike sequences", "list.extend.", "Lists can be modified in place; dictionary keys must be immutable.", "condition", False),
("datastructures", "How do I create an empty set, and what would empty braces create?",
 "Curly braces or the set function", "empty dictionary, a data structure that we discuss in the next section.", "Use set(); {} creates an empty dictionary.", "condition", False),
("inputoutput", "Why should a file be opened in a with block even when the code may raise an exception?",
 "It is good practice to use the with keyword", "point.", "The file is properly closed when the suite finishes, even on an exception.", "paraphrase", False),
("inputoutput", "What does f.read() return after reaching the end of a text file?",
 "If the end of the file has been reached", "string ('').", "An empty string.", "direct", False),
("errors", "Does the finally clause run if the try statement produces no exception?",
 "If a finally clause is present", "not the !try statement produces an exception.", "Yes; it runs whether or not try produces an exception.", "condition", False),
("modules", "When a module is executed as a script, what is the value of __name__?",
 "the code in the module will be executed", 'the __name__ set to "__main__".', "__main__.", "direct", False),
("modules", "Which three sources initialize sys.path for module lookup?",
 "sys.path is initialized from these locations:", "site-packages directory, handled by the site module).", "The script directory (or current directory), PYTHONPATH and the installation-dependent default.", "direct", False),
("classes", "In the classes chapter, which variables are unique to an instance and which are shared by all instances?",
 "Generally speaking, instance variables", "of the class::", "Instance variables are unique to each instance; class variables are shared.", "paraphrase", True),
("classes", "How does an iterator signal that it has no remaining elements to a for loop?",
 "When there are no more elements", "!for loop to terminate.", "Its __next__ method raises StopIteration.", "direct", False),
("venv", "Which pip command writes installed packages in a format that pip install can read?",
 "python -m pip freeze will produce", "but the output uses the format that python -m pip install expects.", "python -m pip freeze.", "paraphrase", False),
]


def main() -> None:
    pages = load_pages(ROOT / "data/pages.jsonl")
    questions = []
    for index, (chapter, query, start, end, answer, kind, filtered) in enumerate(SPECS, 1):
        candidates = []
        for page in pages:
            if page.metadata["chapter"] != chapter:
                continue
            text = canonical(page.text)
            left = text.find(start)
            right = text.find(end, left) if left >= 0 else -1
            if left >= 0 and right >= 0:
                candidates.append((page, text[left:right + len(end)]))
        if not candidates:
            raise ValueError(f"Evidence not found: q{index:02d}: {start} ... {end}")
        page, evidence = candidates[0]
        questions.append({"id": f"q{index:02d}", "split": "dev" if index <= 15 else "test",
            "question": query, "expected_answer": answer, "gold_source_id": page.document_id,
            "gold_page": page.page, "evidence_quote": evidence, "type": kind,
            "filter": {"chapter": chapter} if filtered else {},
            "evidence_verification": "Exact normalized substring in frozen source unit; AI-authored, student review required."})
    target = ROOT / "benchmark/questions.json"
    target.write_text(json.dumps(questions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(questions)} evidence-verified questions (15 dev / 5 test)")


if __name__ == "__main__":
    main()
