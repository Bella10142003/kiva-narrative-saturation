# External ZIP Exclusions

The full computation ran against borrower-level source data in a controlled local work directory. The external ZIP deliberately excludes the following generated or supplied material:

- the original pickle and every raw/private text checkpoint;
- `data/` row-level model and narrative-pool Parquet files;
- `outputs/engine_scores_2025.csv` per-loan triage scores;
- development-only `_dev` outputs and caches;
- all `source/` material: the proposal includes student identifiers and author metadata, the Excel data dictionary includes borrower/location examples, and the prompt/context runners contain embedded imperative text;
- `outputs/country_counts.csv`, whose smallest aggregate cells are below the external privacy threshold; inferential country tables retain only the top 15 high-volume groups;
- redundant generator inspection files outside `audit/`.

The final ZIP retains the complete source code, seven executed aggregate-audit notebooks, frozen specifications, exact aggregate result tables, figure source tables, reports, presentation, speaker materials, and deterministic audit receipts. These exclusions preserve the analysis and judging evidence without distributing linkable borrower-level records.
