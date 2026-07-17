# OMIM Access and Entitlements

How this project reaches OMIM: the API, the bulk download files, and the credentials each needs.

**No credentials in this file.** Both the API key and the download token are secrets and live outside the repo — see [Credentials](#credentials).

## API

| | |
|---|---|
| Host | `api.omim.org` |
| Base URL | `https://api.omim.org/api` |
| Web interface | https://api.omim.org/api/html/index.html |
| API documentation | https://omim.org/help/api |
| Search documentation | https://omim.org/help/search |

Sample request:

```
https://api.omim.org/api/entry?mimNumber=100820&apiKey=<OMIM_API_KEY>
```

Prefer the `ApiKey:` header over the query parameter so the key does not land in server logs, shell history, or referrers. See `omim-api-reference.md` for the full endpoint surface and `omim-search-reference.md` for query syntax.

## Bulk download files

Four files are entitled to this account. Three are served from `data.omim.org` behind a per-account token embedded in the URL path; `mim2gene.txt` is served from the public static path and needs no token.

| File | URL |
|---|---|
| `mim2gene.txt` | `https://omim.org/static/omim/data/mim2gene.txt` (public, no token) |
| `mimTitles.txt` | `https://data.omim.org/downloads/<OMIM_DOWNLOAD_TOKEN>/mimTitles.txt` |
| `genemap2.txt` | `https://data.omim.org/downloads/<OMIM_DOWNLOAD_TOKEN>/genemap2.txt` |
| `morbidmap.txt` | `https://data.omim.org/downloads/<OMIM_DOWNLOAD_TOKEN>/morbidmap.txt` |

### File formats

**Not yet documented — do not guess.** The column layouts are not covered by the API or search documentation. Each file carries a comment header (lines beginning `#`) that describes its own columns and records the generation date. Fetch each file and read its header before writing any parser, and record the real layout here.

What is known so far, subject to that verification:

- All four are tab-delimited text with `#` comment headers.
- `mim2gene.txt` maps MIM numbers to Entrez Gene IDs, gene symbols, and Ensembl IDs, and carries the MIM entry type.
- `mimTitles.txt` maps MIM numbers to their prefix and titles.
- `genemap2.txt` is the gene map — cytogenetic location, gene symbols, phenotypes.
- `morbidmap.txt` is the phenotype-to-gene mapping.

### API vs. downloads

Both surfaces expose overlapping data. Rough division:

- **Downloads** — complete, cheap, no per-request quota, updated daily. Right for building a local index or doing anything set-wide.
- **API** — richer per-entry content (text sections, allelic variants, references, clinical synopses) that the flat files do not carry, plus search. Costs quota per request and caps results.

A design that needs both breadth and depth will likely seed from the downloads and enrich selected entries via the API.

## Credentials

Two distinct secrets, neither in this repo:

| Secret | Used for |
|---|---|
| API key | every `api.omim.org` request |
| Download token | the `data.omim.org` file URLs |

Both were issued in the OMIM entitlement email. When the project starts making live calls, they belong in an untracked environment file (with an `.env.example` documenting the variable names) or the OS keychain, and the untracked file must be in `.gitignore` **before** the first commit that could pick it up.

The download token is a URL path segment, which makes it easy to leak by accident — in a committed script, a `curl` line pasted into an issue, a log, or shell history. Treat any URL containing it as a credential.

## Entitlement and licensing

Access is registered to:

```
Reju Sam John
Health New Zealand
rejusamj@adhb.govt.nz
```

Two consequences worth settling before the project produces anything shareable:

1. **The entitlement is institutional**, granted via a Health New Zealand address. Whatever this project produces sits under the terms of that registration, not a personal one.
2. **OMIM data is copyrighted and its redistribution is restricted.** OMIM grants access under terms that limit onward distribution. Downloaded files and any derived dataset must not be committed to a public repository or otherwise republished without checking those terms first.

The practical rule until confirmed otherwise: **the data files stay out of git**, and anything published — code, docs, examples — carries no bulk OMIM content. Code that fetches the data is fine; the data itself is not ours to hand on.
