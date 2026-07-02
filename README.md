# Olfactory Cultural Evolution of Perfumes since 1900

Data and analysis code reproducing the figures in the paper below: how the notes,
accords, quality, novelty, and copying patterns of perfumes have evolved over the
past century.

## Structure

- **[`dataset/`](dataset)** — the perfume and patent datasets.
- **[`Notebooks/`](Notebooks)** — one notebook per main figure.
- **[`utils/`](utils)** — shared parsing/analysis helpers.
- **[`output/`](output)** — generated figures.

## Quick start

```bash
unzip dataset/Fragrantica.csv.zip -d dataset/   # restore the main dataset
```

Then open any notebook in `Notebooks/` and run it top to bottom.

## Citation

> V. Satarifard, F. Baumann, G. Minsky, L. Sisson, L. M. Haux, C. Laudamiel, and
> N. A. Christakis. *Olfactory Cultural Evolution of Perfumes since 1900.*
> Under Review (2026).
