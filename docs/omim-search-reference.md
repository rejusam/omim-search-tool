# OMIM Search Reference

Search query syntax and indexed fields. Search is SOLR-backed using the extended dismax parser; this document covers the query language and the field names available in each index.

See `omim-api-reference.md` for the HTTP endpoints that accept these queries.

## Query syntax

### Basic search

Enter terms directly:

```
duchenne muscular dystrophy
```

Terms are matched **in any order**, and entries containing all the terms rank higher than entries containing only some. Searches are **case-insensitive**.

**This is an OR-by-default engine.** `blindness hypertelorism` is interpreted as `blindness OR hypertelorism`, not AND. Code that assumes all terms are required will get far more results than expected — require terms explicitly with `+`, or pass the API's `operator=AND` parameter.

### `+` / `-` operators

Preferred over boolean operators — less ambiguous, better control.

| Query | Meaning |
|---|---|
| `+duchenne +muscular dystrophy` | must contain 'duchenne' and 'muscular'; 'dystrophy' optional |
| `+muscular +dystrophy -duchenne` | must contain 'muscular' and 'dystrophy'; must not contain 'duchenne' |
| `+(duchenne muscular dystrophy)` | must contain **any** of the terms |
| `-(duchenne muscular dystrophy)` | must contain **none** of the terms |
| `+"duchenne muscular dystrophy"` | must contain the phrase |
| `+blindness -hypertelorism` | `blindness NOT hypertelorism` |

### Phrase search

```
"duchenne muscular dystrophy"
```

Only entries containing the phrase are returned. Loosen with `~n`, where n is the number of terms allowed between:

```
"duchenne dystrophy"~1
```

matches both "duchenne dystrophy" and "duchenne muscular dystrophy".

Combine with `-`:

```
"muscular dystrophy" -"duchenne gene"
```

### Wildcard search

- `?` — single character
- `*` — multiple characters

```
dystroph*      → dystrophia, dystrophin, dystrophic, dystrophy, …
dystrophi?     → dystrophia, dystrophin, dystrophic — not 'dystrophins'
dystroph??     → dystrophia, dystrophin, dystrophic — not 'dystrophy'
dystro*ia      → wildcard inside a term
dystro??i?
*cortisolism   → leading wildcard: hypocortisolism / hypercortisolism
hy*cortisolism
*glutar*       → catches spelling variants, e.g. 3-methylglutaric acid
```

Leading wildcards are supported (unusual — many Lucene setups disable them).

### Fielded search

**No spaces** between the field name, the colon, and the term / left parenthesis / left quotation mark.

```
title:duchenne
title:duchenne title:muscular title:dystrophy
title:(duchenne muscular dystrophy)      → any order
title:(+duchenne +muscular +dystrophy)   → all terms required
+title:(duchenne muscular dystrophy)     → must contain any of the terms
title:(-duchenne -muscular -dystrophy)   → excludes entries containing all of them
-title:(duchenne muscular dystrophy)     → excludes entries containing any of them
title:"duchenne muscular dystrophy"      → phrase within a field
+title:"duchenne muscular dystrophy"     → phrase required
```

### Boolean operators

`AND`, `OR`, `NOT` are supported but **must be UPPERCASE**. OMIM explicitly recommends `+`/`-` instead.

```
duchenne AND muscular AND dystrophy          ≡ +duchenne +muscular +dystrophy
muscular AND dystrophy NOT duchenne          ≡ +muscular +dystrophy -duchenne
(duchenne AND dystrophy) OR (becker AND dystrophy)
```

### Search grouping

Precedence is ambiguous without parentheses — `muscular AND dystrophy OR duchenne AND gene` is unclear. Group explicitly:

```
(muscular AND dystrophy) OR (duchenne AND gene)
( (muscular AND dystrophy) OR (duchenne AND gene) ) NOT (becker OR Emery-Dreifuss)
```

### Proximity search

```
"muscular dystrophy"~10
```

Terms less than 10 words apart. **Direction-independent** — `muscular … dystrophy` matches the same as `dystrophy … muscular`.

### Term weight boosting

Terms default to weight 1; `^` boosts:

```
muscular dystrophy^10
```

boosts 'dystrophy' by a factor of 10.

### Date search

Applies to date fields (`date_created`, `date_updated`, `cs_date_created`, `cs_date_updated`).

| Query | Meaning |
|---|---|
| `date_updated:2014/7/1` | updated on July 1st, 2014 |
| `date_updated:2014/7` | updated in July 2014 |
| `date_updated:2014` | updated in 2014 |
| `date_updated:2014/7/1-*` | from July 1st 2014 to today |
| `date_updated:2014/7-*` | from July 2014 to today |
| `date_updated:2014-*` | from 2014 to today |
| `date_updated:*-2014/7/1` | from the start to July 1st, 2014 |
| `date_updated:*-2014/7` | from the start to July 2014 |
| `date_updated:*-2014` | from the start to 2014 |
| `date_updated:2014/7/1-2014/10/1` | July 1st to October 1st, 2014 |
| `date_updated:2014/7-2014/10` | July to October 2014 |
| `date_updated:2014-2015` | 2014 to 2015 |
| `date_updated:yesterday` | |
| `date_updated:lastweek` | |
| `date_updated:lastmonth` | |
| `date_updated:lastyear` | |

Format is `YYYY/M/D` — not ISO. Ranges use `-` with `*` as an open bound.

### Cytolocation / genomic coordinate search

Supported by the **gene map index**.

| Query | Meaning |
|---|---|
| `1p36` | entries starting at that band (the pter end) |
| `1:124,300,000` | entries starting at that position |
| `1p36-p32` | entries that start, end, or overlap that region |
| `1p32-p32` | entries that start, end, or overlap that band |
| `1:12,000,000-48,000,000` | entries that start, end, or overlap that region |
| `1:12,000,000-12,000,000` | entries that start, end, or overlap that position |
| `1` or `chr1` | entries on that chromosome |

Coordinates are written with comma thousands separators.

## Search concepts

### Text (unfielded) search

A search with no field specified is a 'text' search. For entries this covers all fields **except the external data fields**. The `Meta Fields` column in the tables below records which fields roll up into `text`.

**External IDs are not in the unfielded index.** To find an approved gene symbol you must field-qualify:

```
approved_gene_symbol:MZT1
approved_gene_symbol:DMD
gene_id:1756
ref_pubmed_id:3294410
```

### Meta fields

Some fields group several others and generally mirror the sections of a MIM entry. `title` searches preferred, alternative, and included titles at once:

```
title:(duchenne muscular dystrophy)
```

Narrow to one with `ti_preferred`, `ti_alternative`, or `ti_included`:

```
ti_preferred:(duchenne muscular dystrophy)
```

Other meta fields: `tx` (text sections), `av` (allelic variants), `cs` (clinical synopsis), `ref` (references), plus the `cs_*` category rollups.

### Restricted-vocabulary fields

```
status:live
status:moved
status:removed
```

### Boolean fields

Values are `true` / `false`:

```
av_exists:true      → only entries with allelic variants
av_exists:false     → only entries without
```

### Prefix search

```
duchenne AND prefix:*
duchenne AND prefix:+
duchenne AND prefix:#
duchenne AND prefix:%
duchenne AND prefix:none
```

---

## Entry search fields

External data (bottom of the table) is **not** included in an unfielded search.

| Field name | Description | Meta fields | Comments |
|---|---|---|---|
| `text` | text meta field | | default search field |
| `number` | mim number | text | key field |
| `prefix` | prefix | text | |
| `title` | title meta field | | |
| `ti_preferred` | preferred title | title, text | |
| `ti_alternative` | alternative title | title, text | |
| `ti_included` | included title | title, text | |
| `gene_symbol` | gene symbol | | |
| `gene_symbol_exists` | presence of a gene symbol | | boolean |
| `status` | status | | live / moved / removed |
| `moved_to` | mim number moved to | | |

### Text sections (`tx` meta field)

Each has a matching `…_exists` boolean.

| Field name | Description |
|---|---|
| `tx_text` | text section |
| `tx_animal_model` | animal model |
| `tx_biochemical_features` | biochemical features |
| `tx_clinical_features` | clinical features |
| `tx_clinical_management` | clinical management |
| `tx_cloning` | cloning |
| `tx_cytogenetics` | cytogenetics |
| `tx_description` | description |
| `tx_diagnosis` | diagnosis |
| `tx_evolution` | evolution |
| `tx_gene_family` | gene family |
| `tx_gene_function` | gene function |
| `tx_gene_structure` | gene structure |
| `tx_gene_therapy` | gene therapy |
| `tx_genetic_variability` | genetic variability |
| `tx_genotype` | genotype |
| `tx_genotype_phenotype_correlations` | genotype phenotype correlations |
| `tx_heterogeneity` | heterogeneity |
| `tx_history` | history |
| `tx_inheritance` | inheritance |
| `tx_mapping` | mapping |
| `tx_molecular_genetics` | molecular genetics |
| `tx_nomenclature` | nomenclature |
| `tx_other_features` | other features |
| `tx_pathogenesis` | pathogenesis |
| `tx_phenotype` | phenotype |
| `tx_population_genetics` | population genetics |

All are in meta fields `tx, text`. The exists flags follow the pattern `<field>_exists` — **except** `tx_nomenclature`, whose flag is documented as **`tx_nomenclatures_exists`** (plural). Treat that as a documented irregularity rather than a typo to correct; verify against the live index before relying on it.

### Allelic variants (`av` meta field)

| Field name | Description | Meta fields | Comments |
|---|---|---|---|
| `av` | allelic variant meta field | | |
| `av_exists` | presence of allelic variants | | boolean |
| `av_number` | number in the format #### | av, text | |
| `av_name` | name | av, text | |
| `av_alternative_names` | included names | av, text | |
| `av_mutations` | mutations | av, text | |
| `av_text` | text | av, text | |
| `av_db_snp` | dbSNP | av, text | |
| `av_clinvar_accession` | ClinVar accession | | |
| `av_gnomad_snp` | SNP in gnomAD | av, text | boolean |

### Clinical synopsis, references, map

| Field name | Description | Meta fields | Comments |
|---|---|---|---|
| `cs` | clinical synopsis meta field | | |
| `cs_exists` | presence of a clinical synopsis | | boolean |
| `cs_*` | the clinical synopsis fields starting with `cs` (see below) | cs, text | |
| `cs_date_created` | clinical synopsis date created | | |
| `cs_date_updated` | clinical synopsis date updated | | |
| `see_also` | see also | text | |
| `ref` | reference meta field | | |
| `ref_author` | author | ref, text | |
| `ref_title` | title | ref, text | |
| `ref_source` | source | ref, text | |
| `ref_pubmed_id` | PubMed ID | ref, text | |
| `ref_article_url` | article url | ref, text | |
| `ref_doi` | doi | ref, text | |
| `genemap_exists` | presence in the gene map, as gene or phenotype | | boolean |
| `phenotype_exists` | presence in the gene map as a phenotype, or a gene with a phenotype | | boolean |
| `chromosome` | chromosome | | 1-22, X, Y, M, U |
| `chromosome_number` | chromosome number | | 1-22, 23, 24, 25, 0 |
| `chromosome_group` | chromosome group | | A autosomal, S XY, M mitochondria, U unset |
| `molecular_series_number` | molecular series number | text | text |
| `molecular_series_exists` | presence in a molecular series | | boolean |
| `phenotypic_series_number` | phenotypic series number | text | text |
| `phenotypic_series_exists` | presence in a phenotypic series | | boolean |
| `phenotype_mapping_key` | phenotype mapping key | | 1, 2, 3, 4 |
| `imprinting_region_exists` | genomic coordinate is within or straddles an imprinted region | | boolean |
| `contributors` | contributors | text | |
| `creator` | creator | text | |
| `date_created` | date created | | date |
| `date_updated` | date updated | | date |

### External data (entry index)

Not searchable without an explicit field name.

| Field name | Description | Comments |
|---|---|---|
| `gene_id` | NCBI gene ID | |
| `gene_id_exists` | | boolean |
| `ncbi_reference_sequence` | NCBI reference sequence | |
| `ncbi_reference_sequence_exists` | | boolean |
| `ncbi_reference_sequence_mane_select_exists` | NCBI reference sequence (MANE Select) | boolean |
| `approved_gene_symbol` | approved gene symbol | |
| `approved_gene_symbol_exists` | | boolean |
| `ensembl_id` | Ensembl ID | |
| `ensembl_id_exists` | | boolean |
| `ensembl_id_select_exists` | Ensembl ID (MANE Select) | boolean |
| `genbank_nucleotide_sequence` | Genbank nucleotide sequence | |
| `genbank_nucleotide_sequence_exists` | | boolean |
| `protein_sequence` | protein sequence | |
| `protein_sequence_exists` | | boolean |
| `uniprot_id` | UniProt ID | |
| `uniprot_id_exists` | | boolean |
| `locus_specific_database_name` | locus specific database name | **currently excluded** |
| `locus_specific_database_url` | locus specific database url | **currently excluded** |
| `locus_specific_database_exists` | | boolean |
| `mgi_id` | MGI ID | |
| `mgi_id_exists` | | boolean |
| `mgi_human_disease` | MGI human disease | boolean |
| `nbk_id` | NBK ID | |
| `flybase_id` | FlyBase ID | |
| `flybase_id_exists` | | boolean |
| `zfin_id` | ZFIN ID | |
| `zfin_id_exists` | | boolean |
| `coriell_disease_name` | Coriell disease name | |
| `coriell_id_exists` | | boolean |
| `orphanet_id` | Orphanet ID | |
| `orphanet_disease_name` | Orphanet disease name | |
| `orphanet_id_exists` | | boolean |
| `decipher_syndrome_name` | DECIPHER syndrome name | **currently excluded** |
| `decipher_syndrome_url` | DECIPHER syndrome url | **currently excluded** |
| `decipher_syndrome_exists` | | boolean |
| `decipher_gene` | DECIPHER gene | boolean |
| `ghr_type` | MedlinePlus Genetics type | `gene` \| `condition` |
| `ghr_title` | MedlinePlus Genetics title | |
| `ghr_id` | MedlinePlus Genetics ID | |
| `ghr_id_exists` | | boolean |
| `omia_id` | OMIA ID | |
| `omia_group` | OMIA group | |
| `omia_id_exists` | | boolean |
| `snomedct_id` | SNOMEDCT ID | |
| `snomedct_id_exists` | | boolean |
| `icd10cm_id` | ICD10CM ID | |
| `icd10cm_id_exists` | | boolean |
| `icd9cm_id` | ICD9CM ID | |
| `icd9cm_id_exists` | | boolean |
| `umls_id` | UMLS ID | |
| `umls_id_exists` | | boolean |
| `disease_ontology_id` | Disease Ontology ID | |
| `disease_ontology_id_exists` | | boolean |
| `genetic_alliance_id` | Genetic Alliance ID | |
| `genetic_alliance_id_exists` | | boolean |
| `gtr` | GTR | boolean |
| `kegg_pathways` | KEGG Pathways | boolean |
| `gwas_catalog` | GWAS Catalog | boolean |
| `clin_gen_dosage` | ClinGen Dosage | boolean |
| `clin_gen_validity` | ClinGen Validity | boolean |
| `monarch` | Monarch | boolean |
| `newborn_screening_name` | newborn screening name | **currently excluded** |
| `newborn_screening_url` | newborn screening url | **currently excluded** |
| `newborn_screening_exists` | | boolean |
| `clinpgx_id` | ClinPGx ID | |
| `clinpgx_id_exists` | | boolean |
| `mondo_id` | MONDO ID | |
| `mondo_id_exists` | | boolean |
| `alliance_genome` | Alliance Genome | boolean |

Note `ghr_*` fields are named for the retired "Genetics Home Reference" but describe **MedlinePlus Genetics**. The API's entry data field is `geneticsHomeReferenceIDs`.

---

## Clinical synopsis search fields

| Field name | Description | Meta fields | Comments |
|---|---|---|---|
| `text` | text meta field | | default search field |
| `number` | mim number | text | key field |
| `prefix` | prefix | text | |
| `cs` | clinical synopsis meta field | | |
| `title` | title meta field | | |
| `ti_preferred` | preferred title | title, cs, text | |

Feature fields. Each has a matching `…_exists` boolean. Category meta fields (`cs_growth`, `cs_head_and_neck`, `cs_cardiovascular`, `cs_respiratory`, `cs_chest`, `cs_abdomen`, `cs_genitourinary`, `cs_skeletal`, `cs_skin_nails_hair`, `cs_neurologic`, `cs_prenatal_manifestations`) have exists flags covering **the category and its subheadings**; leaf flags cover only their own field.

| Field name | Meta fields |
|---|---|
| `cs_inheritance` | cs, text |
| `cs_growth` *(meta)* | |
| `cs_growth_height` | cs_growth, cs, text |
| `cs_growth_weight` | cs_growth, cs, text |
| `cs_growth_other` | cs_growth, cs, text |
| `cs_head_and_neck` *(meta)* | |
| `cs_head_and_neck_head` | cs_head_and_neck, cs, text |
| `cs_head_and_neck_face` | cs_head_and_neck, cs, text |
| `cs_head_and_neck_ears` | cs_head_and_neck, cs, text |
| `cs_head_and_neck_eyes` | cs_head_and_neck, cs, text |
| `cs_head_and_neck_nose` | cs_head_and_neck, cs, text |
| `cs_head_and_neck_mouth` | cs_head_and_neck, cs, text |
| `cs_head_and_neck_teeth` | cs_head_and_neck, cs, text |
| `cs_head_and_neck_neck` | cs_head_and_neck, cs, text |
| `cs_cardiovascular` *(meta)* | |
| `cs_cardiovascular_heart` | cs_cardiovascular, cs, text |
| `cs_cardiovascular_vascular` | cs_cardiovascular, cs, text |
| `cs_respiratory` *(meta)* | |
| `cs_respiratory_nasopharynx` | cs_respiratory, cs, text |
| `cs_respiratory_larynx` | cs_respiratory, cs, text |
| `cs_respiratory_airways` | cs_respiratory, cs, text |
| `cs_respiratory_lung` | cs_respiratory, cs, text |
| `cs_chest` *(meta)* | |
| `cs_chest_external_features` | cs_chest, cs, text |
| `cs_chest_ribs_sternum_clavicle_and_scapulae` | cs_chest, cs, text |
| `cs_chest_breasts` | cs_chest, cs, text |
| `cs_chest_diaphragm` | cs_chest, cs, text |
| `cs_abdomen` *(meta)* | |
| `cs_abdomen_external_features` | cs_abdomen, cs, text |
| `cs_abdomen_liver` | cs_abdomen, cs, text |
| `cs_abdomen_pancreas` | cs_abdomen, cs, text |
| `cs_abdomen_biliary_tract` | cs_abdomen, cs, text |
| `cs_abdomen_spleen` | cs_abdomen, cs, text |
| `cs_abdomen_gastrointestinal` | cs_abdomen, cs, text |
| `cs_genitourinary` *(meta)* | |
| `cs_genitourinary_external_genitalia_male` | cs_genitourinary, cs, text |
| `cs_genitourinary_external_genitalia_female` | cs_genitourinary, cs, text |
| `cs_genitourinary_internal_genitalia_male` | cs_genitourinary, cs, text |
| `cs_genitourinary_internal_genitalia_female` | cs_genitourinary, cs, text |
| `cs_genitourinary_kidneys` | cs_genitourinary, cs, text |
| `cs_genitourinary_ureters` | cs_genitourinary, cs, text |
| `cs_genitourinary_bladder` | cs_genitourinary, cs, text |
| `cs_skeletal` *(meta)* | |
| `cs_skeletal_skull` | cs_skeletal, cs, text |
| `cs_skeletal_spine` | cs_skeletal, cs, text |
| `cs_skeletal_pelvis` | cs_skeletal, cs, text |
| `cs_skeletal_limbs` | cs_skeletal, cs, text |
| `cs_skeletal_hands` | cs_skeletal, cs, text |
| `cs_skeletal_feet` | cs_skeletal, cs, text |
| `cs_skin_nails_hair` *(meta)* | |
| `cs_skin_nails_hair_skin` | cs_skin_nails_hair, cs, text |
| `cs_skin_nails_hair_skin_histology` | cs_skin_nails_hair, cs, text |
| `cs_skin_nails_hair_skin_electron_microscopy` | cs_skin_nails_hair, cs, text |
| `cs_skin_nails_hair_nails` | cs_skin_nails_hair, cs, text |
| `cs_skin_nails_hair_hair` | cs_skin_nails_hair, cs, text |
| `cs_muscle_soft_tissue` *(meta)* | |
| `cs_neurologic` *(meta)* | |
| `cs_neurologic_central_nervous_system` | cs_neurologic, cs, text |
| `cs_neurologic_peripheral_nervous_system` | cs_neurologic, cs, text |
| `cs_neurologic_behavioral_psychiatric_manifestations` | cs_neurologic, cs, text |
| `cs_voice` | cs, text |
| `cs_metabolic_features` | cs, text |
| `cs_endocrine_features` | cs, text |
| `cs_hematology` | cs, text |
| `cs_immunology` | cs, text |
| `cs_neoplasia` | cs, text |
| `cs_prenatal_manifestations` *(meta)* | |
| `cs_prenatal_manifestations_movement` | cs_prenatal_manifestations, cs, text |
| `cs_prenatal_manifestations_amniotic_fluid` | cs_prenatal_manifestations, cs, text |
| `cs_prenatal_manifestations_placenta_and_umbilical_cord` | cs_prenatal_manifestations, cs, text |
| `cs_prenatal_manifestations_maternal` | cs_prenatal_manifestations, cs, text |
| `cs_prenatal_manifestations_deliver` | cs_prenatal_manifestations, cs, text |
| `cs_laboratory_abnormalities` | cs, text |
| `cs_miscellaneous` | cs, text |
| `cs_molecular_basis` | cs, text |

Other fields:

| Field name | Description | Meta fields | Comments |
|---|---|---|---|
| `cs_old_format_exists` | presence of old format | | boolean |
| `cs_contributors` | contributors | text | |
| `cs_creator` | creator | text | |
| `date_created` | date created | | date |
| `date_updated` | date updated | | date |

### External data (clinical synopsis index)

| Field name | Description |
|---|---|
| `cs_snomedct_id` | SNOMEDCT ID |
| `cs_icd10cm_id` | ICD10CM ID |
| `cs_icd9cm_id` | ICD9CM ID |
| `cs_umls_id` | UMLS ID |
| `cs_hpo_id` | HPO ID |

---

## Gene map search fields

| Field name | Description | Meta fields | Comments |
|---|---|---|---|
| `sequence_id` | sequence ID | | key field |
| `chromosome` | chromosome | | 1-22, X, Y |
| `chromosome_number` | chromosome number | | 1-22, 23, 24 |
| `chromosome_group` | chromosome group | | A autosomal, S XY |
| `chromosome_location_start` | start chromosome location | | |
| `chromosome_location_end` | end chromosome location | text | |
| `transcript` | transcript | text | |
| `cyto_location` | cyto location | | |
| `computed_cyto_location` | computed cyto location | | |
| `number` | mim number | text | |
| `gene_symbol` | gene symbol | text | |
| `gene_name` | gene name | text | |
| `references` | references | text | |
| `comments` | comments | text | |
| `molecular_series_number` | molecular series number | text | text |
| `molecular_series_exists` | presence in a molecular series | | boolean |
| `phenotype_exists` | phenotype exists | | boolean |
| `phenotype` | phenotype text | text | |
| `phenotype_number` | phenotype mim number | text | |
| `phenotypic_series_number` | phenotypic series number | text | |
| `phenotypic_series_exists` | presence in a phenotypic series | | boolean |
| `phenotype_mapping_key` | phenotype mapping key | | 1, 2, 3, 4 |
| `phenotype_inheritance` | phenotype inheritance | | see codes below |
| `imprinting_region_exists` | coordinate within or straddling an imprinted region | | boolean |
| `gene_id` | NCBI gene ID | | |
| `approved_gene_symbol` | approved gene symbol | | |
| `ensembl_id` | Ensembl ID | | |
| `mouse_gene_symbol` | mouse gene symbol | | |
| `mouse_mgi_id` | mouse MGI ID | | |

### `phenotype_inheritance` codes

| Code | Meaning |
|---|---|
| `AD` | Autosomal dominant |
| `AR` | Autosomal recessive |
| `PD` | Pseudoautosomal dominant |
| `PR` | Pseudoautosomal recessive |
| `DD` | Digenic dominant |
| `DR` | Digenic recessive |
| `IC` | Isolated cases |
| `ICB` | Inherited chromosomal imbalance |
| `Mi` | Mitochondrial |
| `Mu` | Multifactorial |
| `SMo` | Somatic mosaicism |
| `SMu` | Somatic mutation |
| `XL` | X-linked |
| `XLD` | X-linked dominant |
| `XLR` | X-linked recessive |
| `YL` | Y-linked |

---

## Naming discrepancies to watch

Search field names and API response field names are **not** mechanical transforms of each other. Known mismatches:

| Search field | API response field | Note |
|---|---|---|
| `cs_prenatal_manifestations_deliver` | `prenatalManifestationsDelivery` | 'deliver' vs 'delivery' |
| `cs_chest_ribs_sternum_clavicle_and_scapulae` | `chestRibsSternumClaviclesAndScapulae` | 'clavicle' vs 'clavicles' |
| `tx_nomenclatures_exists` | — | plural, unlike every other `tx_*_exists` |
| `ghr_*` | `geneticsHomeReferenceIDs` | both name the retired GHR; the data is MedlinePlus Genetics |

Chromosome vocabularies also differ by index: the entry index allows `1-22, X, Y, M, U` (`chromosome_number` 1-25, 0) while the gene map index allows only `1-22, X, Y` (`chromosome_number` 1-24).

Do not generate one name from the other in code — map them explicitly.
