# deGlaze

Finds "matched" decomp functions that are really just assembly.

In a matching decompilation, a function written as an `asm` block copied from the disassembly always matches the
original bytes, so objdiff counts it as matched (green) even though nothing was decompiled. A few of those can quietly
inflate progress numbers by a lot (in one project 13 such functions were 35 KB, about 1.75% of the game code).
deGlaze lists every matched function whose bytes come from asm, so you can move it back to unmatched and keep
the numbers honest.

## Requirements
- Python 3.6 or newer, no packages.
- A [decomp-toolkit](https://github.com/encounter/decomp-toolkit) / dtk-template project with an objdiff
  `report.json` (`ninja` builds it as `build/<version>/report.json`).

## Use
```
python3 deglaze.py --project path/to/your/dtk/project
python3 deglaze.py --project . --own game,engine            # only these progress categories are your own decomp
python3 deglaze.py --project . --own game --all --tsv hits.tsv
python3 deglaze.py --project . --scan drafts/                # also check source drafts outside the build
```
`--help` prints every option.

## What it reports
For each unit in the report that has a source file (and the local headers it includes):
- `asm fn`: a function declared `asm` (MWCC asm function)
- `inline`: an asm statement inside a C/C++ function (`asm { }`, `asm(...)`, `__asm`, `__asm__`, `asm volatile`)
- `asm stmt`: a file-level asm statement

Each hit shows whether objdiff counts the function as matched, and `copied?` when the asm looks pasted from a
disassembler (dtk labels such as `L_80xxxxxx`, `lbl_80xxxxxx`, `jumptable_80xxxxxx`, address comments, `opword`,
raw `.long` words). At the end it prints what the matched-code percentage would be without them.

Library code (the console SDK, the C runtime, middleware) often has real asm in its original source. Pass your own
categories with `--own`: asm in those always counts as glaze; asm in other categories only fails the check when it
looks copied.

Exit status 1 if any glaze was found, else 0, so it can gate a build or a CI job.

## Limits
- Finds asm by keyword. Code smuggled in some other way (raw bytes in a data array that gets called, an assembler
  `.s` file in the build) is not detected.
- `copied?` only catches pastes that kept their labels; a cleaned-up paste looks like hand-written asm. Read the code.
- Matching a source name to the report's function is by name (C++ `Class::method` to `Class__method...`); a hit it
  cannot match is still listed, without a size.
