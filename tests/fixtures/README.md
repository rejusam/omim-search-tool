# Test fixtures

`search_response.json` is a small `entry/search` response with
`include=geneMap`, used by the offline test suite.

**Source:** synthetic values, but the **structure is reconciled against a live
OMIM run** (2026-07-19). The field names, nesting, and value formats match what
the API actually returns; only the identifiers and names are made up so no real
OMIM data is stored here.

The fixture deliberately covers the three real response shapes:

1. **Phenotype entry** (prefix `#`): `phenotypeMapList` sits directly on the
   entry, and each phenotype map embeds the gene and location fields
   (`geneSymbols`, `approvedGeneSymbols`, `cytoLocation`, `chromosomeSymbol`).
   These entries have no `geneName`.
2. **Gene entry** (prefix `*`): a single `geneMap` dict carries the gene fields
   (including `geneName`) plus a nested `phenotypeMapList`. The nested phenotype
   maps carry only phenotype fields, so gene columns fall back to the `geneMap`.
3. **No-map entry** (prefix `?`): neither `geneMap` nor `phenotypeMapList`, so
   the gene and phenotype columns are blank.

Note that `mimNumber` and `phenotypeMappingKey` come back as strings, not
integers.
