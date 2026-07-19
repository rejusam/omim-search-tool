# OMIM API Reference

Condensed reference for the OMIM REST API (`api.omim.org`).

See `omim-access.md` for this project's entitlements, credentials, and the bulk download files, and `omim-search-reference.md` for search query syntax.

## URL structure

```
/api/[handler]?[parameters]
/api/[handler]/[component]?[parameters]
/api/[handler]/[action]?[parameters]
```

- **handler** — the data object (`entry`, `clinicalSynopsis`, `geneMap`, `search`, `status`, `apiKey`).
- **component** — optional; a data component within the object (e.g. `referenceList` within an entry).
- **action** — optional; an operation on the object (e.g. `search`).

Read-only database: **GET is the only method** for public access. Everything else errors, except the `apiKey` handler, which takes POST/DELETE to add/remove the key from cookies.

## Authentication

An API key is required on **every** request. Allocated per developer by OMIM; not shareable. Three ways to pass it:

```
ApiKey: <key>                      # HTTP header
Cookie: ApiKey=<key>               # cookie
https://api.omim.org/…?apiKey=<key>  # query parameter (name is case-sensitive)
```

Prefer the header. Never commit the key.

## Generic parameters

| Parameter | Description |
|---|---|
| `format` | Response format: `json` or `xml` (e.g. `format=json`). Supported by all handlers. |

## Limits and pagination

- Entries and clinical synopses: **20 per request** if any `include` is specified; otherwise unlimited.
- Gene map entries: **100 per request**.
- Batch with `start` and `limit`:

```
…start=0&limit=20
…start=20&limit=20
…start=40&limit=20
```

## Compression

gzip is supported and reduces responses ~4-5x. Some clients enable it automatically; others need it set explicitly.

```
Accept-Encoding: gzip
```

curl does not enable it by default:

```
curl -H "Accept-Encoding: gzip" "https://api.omim.org/api/…" | gunzip
```

## Host

```
api.omim.org
```

HTML interface for exploring URL structure: https://api.omim.org/api/html

## HTTP status codes

| Status | Name | Description |
|---|---|---|
| 200 | OK | Request was successful |
| 400 | Bad Request | URL was incorrect |
| 401 | Unauthorized | API key invalid or inactive |
| 404 | Not Found | Requested data does not exist |
| 429 | Too Many Requests | Quota for the API key exceeded |
| 500 | Internal Server Error | Internal server error |

---

## Handler: `entry`

### Default (no action)

Requires `mimNumber`:

```
https://api.omim.org/api/entry?mimNumber=100100
https://api.omim.org/api/entry?mimNumber=100100&mimNumber=100200
https://api.omim.org/api/entry?mimNumber=100100,100200
```

Returns MIM number, prefix, status, titles.

### `include` parameter

| Value | Description |
|---|---|
| `text` | Text field sections |
| `existFlags` | 'exists' flags (clinical synopsis, allelic variant, gene map, phenotype map) |
| `allelicVariantList` | Allelic variant list |
| `clinicalSynopsis` | Clinical synopsis |
| `seeAlso` | 'see also' field |
| `referenceList` | Reference list |
| `geneMap` | Gene map / phenotype map data |
| `externalLinks` | External links |
| `contributors` | 'contributors' field |
| `creationDate` | 'creation date' field |
| `editHistory` | 'edit history' field |
| `dates` | Dates data |
| `all` | All of the above |

Repeatable or comma-delimited:

```
…&include=text&include=geneMap
…&include=text,geneMap
```

`exclude` removes unwanted sections:

```
…&include=all&exclude=clinicalSynopsis
```

**Only retrieve what is needed** — unneeded data makes requests slower.

### Text sections

`include=text` returns the entire text, which can be long. Narrow it with a colon:

```
https://api.omim.org/api/entry?mimNumber=100100&include=text:clinicalFeatures
```

| Section name | Section title |
|---|---|
| `animalModel` | Animal Model |
| `biochemicalFeatures` | Biochemical Features |
| `clinicalFeatures` | Clinical Features |
| `clinicalManagement` | Clinical Management |
| `cloning` | Cloning and Expression |
| `cytogenetics` | Cytogenetics |
| `description` | Description |
| `diagnosis` | Diagnosis |
| `evolution` | Evolution |
| `geneFamily` | Gene Family |
| `geneFunction` | Gene Function |
| `geneStructure` | Gene Structure |
| `geneTherapy` | Gene Therapy |
| `geneticVariability` | Genetic Variability |
| `genotype` | Genotype |
| `genotypePhenotypeCorrelations` | Genotype/Phenotype Correlations |
| `heterogeneity` | Heterogeneity |
| `history` | History |
| `inheritance` | Inheritance |
| `mapping` | Mapping |
| `molecularGenetics` | Molecular Genetics |
| `nomenclature` | Nomenclature |
| `otherFeatures` | Other Features |
| `pathogenesis` | Pathogenesis |
| `phenotype` | Phenotype |
| `populationGenetics` | Population Genetics |
| `text` | Text (unfielded section at the start of the entry) |

### `entry/search`

Search is SOLR-backed, using the extended dismax parser.

| Parameter | Description |
|---|---|
| `search` | The search (**required**) |
| `filter` | The filter (optional) |
| `fields` | Defaults to `number^5 title^3 default` |
| `sort` | Defaults to `score desc` |
| `operator` | `AND` requires returned documents to contain all terms |
| `start` | Start offset, default 0 |
| `limit` | Number of results, default 10 |
| `retrieve` | `geneMap` or `clinicalSynopsis` — retrieve those instead of the entries themselves |

All the `include`/`exclude` parameters above also apply.

```
https://api.omim.org/api/entry/search?search=duchenne&start=0&limit=20
https://api.omim.org/api/entry/search?search=duchenne&start=0&limit=20&include=geneMap
```

Useful sort orders (any entry-index search field works; **the direction `asc`/`desc` is required**):

| Sort | Meaning |
|---|---|
| `score desc` | Descending score |
| `score desc, prefix_sort desc` | Descending score, then descending prefix sort |
| `date_created desc` / `date_created asc` | By creation date |
| `date_updated desc` / `date_updated asc` | By update date |

**Handler/action flip** — these are equivalent:

```
https://api.omim.org/api/entry/search?search=duchenne&start=0&limit=20&include=geneMap
https://api.omim.org/api/search/entry?search=duchenne&start=0&limit=20&include=geneMap
```

### `entry/allelicVariantList`

```
https://api.omim.org/api/entry/allelicVariantList?mimNumber=100100
```

### `entry/referenceList`

```
https://api.omim.org/api/entry/referenceList?mimNumber=100100
```

### Entry data fields

> **Observed vs documented (verified against a live run, 2026-07-19).** The
> field tree below follows OMIM's published documentation, but the live
> `entry/search?include=geneMap` response differs in an important way: an entry
> does **not** carry a `geneMapList`. Instead each entry has **either** a
> singular `geneMap` object (gene entries, prefix `*`/`%`/`+` — with `geneName`
> and a nested `geneMap.phenotypeMapList`) **or** a `phenotypeMapList` directly
> on the entry (phenotype entries, prefix `#` — with the gene/location fields
> embedded inside each `phenotypeMap`, and no `geneName`). Some entries have
> neither. Also, `mimNumber` and `phenotypeMappingKey` are returned as strings,
> and some fields (e.g. `phenotypeInheritance`) may be JSON `null`. Parse
> against the observed shape, not this tree.

```
omim
  entryList
    entry
      prefix
      mimNumber
      titles
        preferredTitle          # title and symbol, delimited with ';'
        includedTitles          # titles delimited with ';;', title/symbols with ';'
      status                    # 'live', 'moved', 'removed'
      movedTo                   # target entry MIM number if moved
      clinicalSynopsisExists    # true|false, set if 'existFlags' include was set
      allelicVariantExists      # "
      geneMapExists             # "
      phenotypeMapExists        # "
      phenotypicSeriesExists    # "
      textSectionList           # text sections in order
        textSection
          textSectionName
          textSectionTitle
          textSectionContent
      allelicVariantList
        allelicVariant
          number
          status                # 'live', 'moved', 'removed'
          movedTo
          name
          alternativeNames
          mutations
          text
          clinvarAccessions     # comma-delimited ClinVar accessions
          dbSnps                # comma-delimited SNPs
          gnomadSnps
      seeAlso                   # see-also list, delimited with ';'
      referenceList
        reference
          mimNumber
          referenceNumber
          authors
          title
          source
          pubmedID
          articleUrl
          doi
      geneMapList
        geneMap
          sequenceID
          chromosome                # 1-24
          chromosomeSymbol          # 1-22, X, Y
          chromosomeSort
          chromosomeLocationStart   # if available
          chromosomeLocationEnd     # if available
          transcript                # if available
          cytoLocation
          computedCytoLocation      # if available
          mimNumber
          molecularSeriesNumber     # comma-delimited
          geneSymbols               # comma-delimited
          geneName
          references
          comments
          mouseGeneSymbol
          mouseMgiID
          approvedGeneSymbols
          geneIDs
          ensemblIDs
          phenotypeMapList
            phenotypeMap
              mimNumber
              phenotype
              phenotypeMimNumber
              phenotypicSeriesNumber  # comma-delimited
              phenotypeMappingKey
              phenotypeInheritance
      phenotypeMapList
        phenotypeMap
          mimNumber
          phenotype
          phenotypeMimNumber
          phenotypicSeriesNumber
          phenotypeMappingKey
          phenotypeInheritance
          sequenceID                # gene map sequence ID
          chromosome
          chromosomeSymbol
          chromosomeSort
          chromosomeLocationStart
          chromosomeLocationEnd
          transcript
          cytoLocation
          computedCytoLocation
          geneSymbols
          approvedGeneSymbols
          geneIDs
          ensemblIDs
      externalLinks
      contributors
      creationDate
      editHistory
      dates
        dateCreated             # web date
        epochCreated            # unix epoch
        dateUpdated             # web date
        epochUpdated            # unix epoch
```

#### `externalLinks` sub-fields

Note the unusual delimiters — several fields are triple-semicolon delimited lists of double-semicolon delimited tuples.

| Field | Format |
|---|---|
| `geneIDs` | comma-delimited Entrez gene IDs |
| `hgncID` | HGNC ID |
| `ensemblIDs` | triple-colon delimited list of comma-delimited Ensembl ID pairs |
| `approvedGeneSymbols` | comma-delimited |
| `ncbiReferenceSequences` | comma-delimited |
| `genbankNucleotideSequences` | comma-delimited |
| `proteinSequences` | comma-delimited |
| `uniProtIDs` | comma-delimited |
| `locusSpecificDBs` | triple-semicolon delimited name/url tuples; each tuple double-semicolon delimited |
| `mgiIDs` | comma-delimited MGI IDs |
| `mgiHumanDisease` | flag (true\|false) |
| `nbkIDs` | triple-semicolon delimited list of double-semicolon delimited NBK ID / clinical disease name pairs |
| `flybaseIDs` | comma-delimited |
| `zfinIDs` | comma-delimited |
| `coriellDiseases` | triple-semicolon delimited list of double-semicolon delimited entries |
| `orphanetDiseases` | triple-semicolon delimited list of double-semicolon delimited Orphanet ID / disease pairs |
| `decipherSyndromes` | DECIPHER syndromes |
| `decipherGene` | flag (true\|false) |
| `geneticsHomeReferenceIDs` | |
| `omiaIDs` | |
| `snomedctIDs` | |
| `icd10cmIDs` | |
| `icd9cmIDs` | |
| `umlsIDs` | |
| `diseaseOntologyIDs` | |
| `geneticAllianceIDs` | |
| `gtr` | |
| `keggPathways` | |
| `gwasCatalog` | |
| `clinGenDosage` | |
| `clinGenValidity` | |
| `monarch` | |
| `newbornScreening` | |
| `clinpgxID` | |
| `mondoID` | |
| `allianceGenome` | |

### Entry allelic variant data (`entry/allelicVariantList`)

```
omim
  allelicVariantLists
    allelicVariantList
      allelicVariant
        prefix
        mimNumber
        preferredTitle
        number
        status            # 'live', 'moved', 'removed'
        movedTo
        name
        alternativeNames
        mutations
        text
        dbSNPs            # comma-delimited
```

### Entry reference data (`entry/referenceList`)

```
omim
  referenceLists
    referenceList
      reference
        mimNumber
        referenceNumber
        authors
        title
        source
        pubmedID
        articleUrl
        doi
```

---

## Handler: `clinicalSynopsis`

### Default (no action)

```
https://api.omim.org/api/clinicalSynopsis?mimNumber=100100
https://api.omim.org/api/clinicalSynopsis?mimNumber=100100&mimNumber=100200
https://api.omim.org/api/clinicalSynopsis?mimNumber=100100,100200
```

Returns MIM number, prefix, status, titles.

### `include` parameter

| Value | Description |
|---|---|
| `clinicalSynopsis` | The clinical synopsis |
| `existFlags` | 'exists' flags |
| `externalLinks` | External links |
| `contributors` | Contributors |
| `creationDate` | Creation date |
| `editHistory` | Edit history |
| `dates` | Dates |
| `all` | All of the above |

`exclude` works the same as for `entry`:

```
…&include=all&exclude=externalLinks
```

### `clinicalSynopsis/search`

SOLR-backed, extended dismax.

| Parameter | Description |
|---|---|
| `search` | The search (**required**) |
| `filter` | Optional |
| `fields` | Defaults to `number^5 title^3 default` |
| `sort` | Defaults to `score desc` |
| `start` | Default 0 |
| `limit` | Default 10 |

```
https://api.omim.org/api/clinicalSynopsis/search?search=disorder&start=0&limit=20
```

Same sort orders as `entry/search`. Same handler/action flip:

```
https://api.omim.org/api/search/clinicalSynopsis?search=disorder&start=0&limit=20
```

### Clinical synopsis data

Top level:

```
omim
  clinicalSynopsisList
    clinicalSynopsis
      mimNumber
      prefix
      preferredTitle    # taken from the MIM entry
      …feature fields…
      …Exists flags…
      oldFormat         # old-format synopsis, remapped to new format
      externalLinks
      contributors
      creationDate
      editHistory
      dates
        dateCreated / epochCreated / dateUpdated / epochUpdated
```

Feature fields — **values within each field are delimited with `;`** and include IDs for UMLS, SNOMEDCT, ICD10CM, ICD9CM and HPO:

```
inheritance
growth, growthHeight, growthWeight, growthOther
headAndNeck, headAndNeckHead, headAndNeckFace, headAndNeckEars, headAndNeckEyes,
  headAndNeckNose, headAndNeckMouth, headAndNeckTeeth, headAndNeckNeck
cardiovascular, cardiovascularHeart, cardiovascularVascular
respiratory, respiratoryNasopharynx, respiratoryLarynx, respiratoryAirways, respiratoryLung
chest, chestExternalFeatures, chestRibsSternumClaviclesAndScapulae, chestBreasts, chestDiaphragm
abdomen, abdomenExternalFeatures, abdomenLiver, abdomenPancreas, abdomenBiliaryTract,
  abdomenSpleen, abdomenGastrointestinal
genitourinary, genitourinaryExternalGenitaliaMale, genitourinaryExternalGenitaliaFemale,
  genitourinaryInternalGenitaliaMale, genitourinaryInternalGenitaliaFemale,
  genitourinaryKidneys, genitourinaryUreters, genitourinaryBladder
skeletal, skeletalSkull, skeletalSpine, skeletalPelvis, skeletalLimbs, skeletalHands, skeletalFeet
skinNailsHair, skinNailsHairSkin, skinNailsHairSkinHistology,
  skinNailsHairSkinElectronMicroscopy, skinNailsHairNails, skinNailsHairHair
muscleSoftTissue
neurologic, neurologicCentralNervousSystem, neurologicPeripheralNervousSystem,
  neurologicBehavioralPsychiatricManifestations
voice
metabolicFeatures
endocrineFeatures
hematology
immunology
neoplasia
prenatalManifestations, prenatalManifestationsMovement, prenatalManifestationsAmnioticFluid,
  prenatalManifestationsPlacentaAndUmbilicalCord, prenatalManifestationsMaternal,
  prenatalManifestationsDelivery
laboratoryAbnormalities
miscellaneous
molecularBasis
```

Every feature field has a corresponding `…Exists` flag (e.g. `growthExists`, `headAndNeckEyesExists`). Two flag semantics:

- **(i)** — top-level category flags (`growthExists`, `headAndNeckExists`, `cardiovascularExists`, `respiratoryExists`, `chestExists`, `abdomenExists`, `genitourinaryExists`, `skeletalExists`, `skinNailsHairExists`, `neurologicExists`, `prenatalManifestationsExists`, `laboratoryAbnormalitiesExists`): true if **this or any of its subheadings** contain data.
- **(ii)** — leaf flags (everything else, including `inheritanceExists`): true if **this field itself** contains data.

---

## Handler: `geneMap`

### Default (no action)

| Parameter | Description |
|---|---|
| `sequenceID` | Sequence ID in the gene map — sequential integers, no breaks |
| `mimNumber` | The MIM number |
| `chromosome` | 1-22, 23 (X), 24 (Y), 25 (M), or `X`, `Y`, `M` (mitochondria), `A` (autosomal group), `S` (XY group) |
| `chromosomeSort` | Sub-parameter of `chromosome`; sequential integers, no breaks |
| `start` | Start offset, default 0 — **may be negative** when getting a list from a sequence ID |
| `limit` | Number of entries, default 10 |
| `phenotypeExists` | `true` returns only entries with phenotypes, `false` only those without; default returns all |

**`sequenceID` and `chromosomeSort` are not stable beyond the scope of a day** — the gene map is rebuilt daily. Do not persist them as identifiers.

```
https://api.omim.org/api/geneMap?mimNumber=100100
https://api.omim.org/api/geneMap?mimNumber=100100&mimNumber=100200
https://api.omim.org/api/geneMap?mimNumber=100100,100200

https://api.omim.org/api/geneMap?sequenceID=10
https://api.omim.org/api/geneMap?sequenceID=10&limit=10
https://api.omim.org/api/geneMap?sequenceID=20&limit=10
https://api.omim.org/api/geneMap?sequenceID=20&start=-4&limit=10

https://api.omim.org/api/geneMap?chromosome=1&start=0&limit=10
https://api.omim.org/api/geneMap?chromosome=1&start=10&limit=10
https://api.omim.org/api/geneMap?chromosome=1&chromosomeSort=10&limit=10
https://api.omim.org/api/geneMap?chromosome=1&chromosomeSort=1&start=1&limit=10
```

### `geneMap/search`

| Parameter | Description |
|---|---|
| `search` | The search (**required**) |
| `filter` | Optional |
| `fields` | Defaults to `default` |
| `sort` | Defaults to `score desc` |
| `start` | Default 0 |
| `limit` | Default 10 |

```
https://api.omim.org/api/geneMap/search?search=kinase&start=0&limit=20
https://api.omim.org/api/search/geneMap?search=kinase&start=0&limit=20
```

Useful sorts: `score desc`, `chromosome_number asc`, `chromosome_number asc, chromosome_location_start asc`.

### Gene map data

```
omim
  listResponse
    chromosome          # 1-24
    chromosomeSymbol    # 1-22, X, Y
    totalResults
    startIndex
    endIndex
    geneMapList
      geneMap
        sequenceID
        chromosome
        chromosomeSymbol
        chromosomeSort
        chromosomeLocationStart   # if available
        chromosomeLocationEnd     # if available
        transcript                # if available
        cytoLocation
        computedCytoLocation      # if available
        mimNumber
        molecularSeriesNumber     # comma-delimited
        geneSymbols               # comma-delimited
        geneName
        references
        comments
        mouseGeneSymbol
        mouseMgiID
        approvedGeneSymbols
        geneIDs
        ensemblIDs
        phenotypeMapList
          phenotypeMap
            mimNumber
            phenotype
            phenotypeMimNumber
            phenotypicSeriesNumber  # comma-delimited
            phenotypeMappingKey
            phenotypeInheritance
```

---

## Handler: `search`

Used for searching; behaviour is covered under each handler above (the handler/action flip).

### Search response data

```
omim
  searchResponse
    search
    expandedSearch
    parsedSearch
    searchSuggestion
    searchSpelling
    filter
    expandedFilter
    fields
    searchReport
    totalResults
    startIndex
    endIndex
    sort
    searchTime
    *List              # entry / clinicalSynopsis / geneMap / phenotypeMap list
```

---

## Handler: `status`

Check API status:

```
https://api.omim.org/api/status
```

---

## Handler: `apiKey`

Exists only to support the API HTML interface — sets the key in browser cookies.

| Parameter | Description |
|---|---|
| `apiKey` | The API key |

```
POST   https://api.omim.org/api/apiKey?apiKey=foo   # set cookie
DELETE https://api.omim.org/api/apiKey              # remove cookie
```

---

## Search internals

Search is SOLR with the extended dismax parser. Relevant documentation:

- OMIM Search Help
- OMIM Search Fields
- Apache SOLR / Apache Lucene
- SOLR Help / SOLR Searching Help
