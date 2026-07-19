# OMIM Search Tool

A guide for running searches and reading the results. No programming knowledge needed.

## 1. What this does

This tool searches OMIM (Online Mendelian Inheritance in Man — the catalog of
human genes and genetic conditions) for keywords you choose, such as a
disease or syndrome name, and saves what it finds as a spreadsheet on your
computer. You answer a few plain-English questions on screen; it does the
rest.

## 2. One-time setup on Windows

You only need to do this once on a given computer.

1. Go to [python.org](https://www.python.org/downloads/) and download
   Python. Run the installer.
2. On the first install screen, tick the box **"Add Python to PATH"**
   before clicking Install. This step is easy to miss and the tool will not
   run without it.
3. Open **Command Prompt** (click Start, type `cmd`, press Enter).
4. In Command Prompt, move into the folder that contains this tool. For
   example, if it is in your Documents folder under `omim-search`, type:

   ```
   cd Documents\omim-search
   ```

5. Install the tool's two small dependencies by typing:

   ```
   pip install -r requirements.txt
   ```

   This downloads and installs everything the tool needs. It only has to be
   done once per computer, not before every search.

## 3. The API key

To use OMIM's search service, the tool needs an API key — a long password
that OMIM issued to you (or to your lab/institution) by email when your
account was approved. Look for that entitlement email if you don't already
have the key saved somewhere.

The first time you run the tool, it will ask you to paste this key in, and
it will save it to a file called `config.ini` next to the tool. After that
first time, it will not ask again on that computer — it remembers the key
for every future search.

**Treat this key like a password.** It is tied to you or your institution.
Do not share it, email it to colleagues, or paste it into chat messages. If
someone else needs to run searches, they should request their own key from
OMIM rather than use yours.

## 4. Running a search

Open Command Prompt, `cd` to the tool's folder as in step 2, and type:

```
python omim_search.py
```

You'll be asked whether you want a guided search or an expert one:

```
Guided search [g] or expert raw query [e]?
```

Type `g` and press Enter — this is the mode almost everyone should use (see
section 9 for the expert option).

You'll then see two lines of instructions, followed by three prompts you
answer one after another. The first two lines are instructions; you only
type answers at the three prompts below.

Instructions (nothing to type here):

```
Enter search words. Separate several words with commas.
Leave a line blank to skip it.
```

The three prompts:

```
Find entries containing ANY of these words:
Words that MUST appear:
Words to EXCLUDE:
```

**Worked example.** Say you want anything OMIM has about neuropathy,
including the alternate name "neuronopathy". At the first prompt, type:

```
Find entries containing ANY of these words: neuropathy, neuronopathy
```

Then leave the next two prompts blank — just press Enter twice, since you
don't need to require any other word or exclude anything.

The tool then shows you the exact search it is about to run and asks for
confirmation:

```
Query: +(neuropathy neuronopathy)
Run this search? [y/n]
```

Type `y` and press Enter. It's fine if the query text looks a little
technical — it's just OMIM's way of writing "either of these words."

The tool then tells you how many matching entries OMIM found, and asks how
many you want:

```
Fetch [a]ll, a [n]umber, or [c]ancel?
```

Type `a` to get everything, `n` if you only want a smaller number (it will
then ask how many), or `c` to cancel and start over. When it finishes, it
prints the location of the results file.

## 5. Understanding the output

Each search creates its own new folder inside a `results` folder next to the
tool, named after your search and the date and time, for example:

```
results\omim_neuropathy_neuronopathy_20260717-1420\
```

Inside that folder are four files. **Open `results.xlsx` in Excel — this is
the one you want.** Do not open the `.csv` files directly in Excel: Excel
has a habit of "helpfully" mangling certain gene names (for example turning
the gene symbol `SEPT9` into a date) when it opens a plain csv file. The
`results.xlsx` file is built to avoid that problem, so it is always the safe
choice. The `.csv` files and the `raw.json` file are there only as backups
for anyone doing further technical processing — you can ignore them.

`results.xlsx` has three tabs at the bottom of the Excel window:

- **Entries** — one row per OMIM entry (roughly, one row per gene or
  condition record) that matched your search.
- **Phenotypes** — one row per specific condition (phenotype) linked to an
  entry, useful if you want to filter or sort by a particular condition or
  its inheritance pattern.
- **Search info** — a short summary of what was searched, when, how many
  results there were, and a licence note (see section 8).

**Important — the Entries and Phenotypes tabs will usually have different
numbers of rows, and that is expected, not an error.** An entry linked to
several different conditions appears once on the Entries tab but several
times on the Phenotypes tab, once per condition. An entry that is only about
a gene, with no specific condition attached, appears on the Entries tab but
will not appear on the Phenotypes tab at all. Neither tab is missing data —
they are just organized two different ways for two different questions.

**Some cells will be blank, and that is also normal.** OMIM does not hold
every kind of information for every entry, so a cell is left empty when OMIM
has nothing to put there. For example, the `gene_name` cell is blank for an
entry that describes a condition rather than a gene, and the gene and
inheritance columns are blank for an entry that has no gene or condition data
recorded. A blank cell means "OMIM has no value here", not "the tool missed
something".

## 6. What each column means

**Entries tab and Phenotypes tab both share these columns:**

| Column | What it means |
|---|---|
| `mim_number` | The OMIM catalog number for this entry — use it to look the entry up directly on omim.org. |
| `preferred_title` | OMIM's official name for the entry (gene or condition). |
| `approved_gene_symbol` | The official gene symbol (e.g. `DMD`), if the entry is about a gene. |
| `gene_name` | The full name of the gene, spelled out. |
| `cyto_location` | Where the gene sits on the chromosome (its cytogenetic location), e.g. `Xp21.2-p21.1`. |

**Phenotypes tab only:**

| Column | What it means |
|---|---|
| `phenotype` | The name of the specific condition linked to this entry. |
| `phenotype_inheritance` | How the condition is inherited (e.g. autosomal dominant, X-linked recessive), where OMIM records it. |

**Link columns (both tabs):**

| Column | What it means |
|---|---|
| `omim_url` / `entry_url` | A web link straight to the OMIM entry page. |
| `phenotype_url` | A web link straight to that specific condition's OMIM page. |

Click any of the link columns and it will open the relevant page on
omim.org in your browser.

## 7. When something goes wrong

- **"The API key's quota is exhausted"** — your key has a daily limit on
  how many searches it can run, and you've reached it for today. Wait and
  try again tomorrow; nothing is broken.
- **"The API key was rejected"** — the saved key is no longer accepted by
  OMIM. Delete the `config.ini` file next to the tool and run
  `python omim_search.py` again; it will ask you to paste the key in fresh.
- **Anything else** (an error message you don't recognize, the tool won't
  start, results look wrong) — contact `<add contact name and email>` for
  help. Include the exact wording of any error message you see.

## 8. A note on the data

OMIM's data is licensed and copyrighted — it is not ours to give away.
Please do not forward the `results.xlsx` file, the other files in the
results folder, or any part of their contents to anyone outside this
project, and do not post or republish them anywhere. Use them for your own
review and analysis only.

The tool's own source code is released under the MIT License (see the
`LICENSE` file). That licence covers this software only. It does **not**
cover OMIM's data or OMIM's documentation, which remain subject to OMIM's own
terms as described above.

## 9. Expert mode (advanced — most people can skip this)

If you know exactly what OMIM query syntax you want to write yourself
instead of answering the guided questions, choose `e` (expert) at the first
prompt and type your own raw query. The full query syntax — how to require
or exclude words, search specific fields, use wildcards, and so on — is
documented in `docs/omim-search-reference.md`. Ordinary guided searches
(section 4) do not need any of this.
