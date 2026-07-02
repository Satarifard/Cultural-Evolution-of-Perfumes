# Dataset

Data used by the notebooks in [`../Notebooks`](../Notebooks). All files are
comma-separated tables. Several columns in `Fragrantica.csv` are JSON-encoded
(see below); the notebooks parse them with helpers in [`../utils`](../utils).

> **Unzip first.** `Fragrantica.csv` (~98 MB uncompressed) is stored as
> `Fragrantica.csv.zip` (~23 MB) to stay within GitHub's file-size limits.
> Before running any notebook, unzip it in place so that `Fragrantica.csv`
> sits next to this README:
>
> ```bash
> unzip Fragrantica.csv.zip
> ```

## Files

| File | Rows | Description |
|------|-----:|-------------|
| `Fragrantica.csv.zip` | 92,589 | **Primary dataset.** Perfume records scraped from Fragrantica, used throughout the paper (Figures 1–4). Unzip to `Fragrantica.csv` before use. |
| `Aromo.csv` | 78,409 | Independent perfume database (Aromo). Used to cross-validate note/accord coverage and ratings (Figure S1). |
| `Parfumo.csv` | 59,315 | Independent perfume database (Parfumo). Second cross-validation source (Figure S1). |
| `FIG.csv` | 3,159 | Fragrance-ingredient **patent** records (CAS number, descriptors, priority/grant dates). Used for the patents-vs-vocabulary analysis (Figure S6). |

## Columns

**`Fragrantica.csv`** (21 cols): `id`, `perfume name`, `brand`, `year`,
`notes`, `accords`, `fragrance pyramid`, `perfumer`, `gender`,
`this_perfume_reminds_ids`, `Total_votes`, `rating`, `price_rating`,
`longevity_rating`, `sillage_rating`, `gender_rating`, `relation`,
`Country`, `Main Activity`, `Type`, `Parent Company`.
JSON-encoded columns: `notes` and `accords` (item → weight), `price_rating`
and the other `*_rating` fields (rating value → vote count), and
`this_perfume_reminds_ids` (list of the perfume `id`s that reviewers say this
scent resembles — the basis for the resemblance/copy network).

**`Aromo.csv`** (13 cols): `name`, `brand`, `type`, `year`, `segment`,
`rating_value`, `rating_count`, `perfumers`, `families`, `top_notes`,
`middle_notes`, `bottom_notes`, `users_notes`.

**`Parfumo.csv`** (12 cols): `Number`, `Name`, `Brand`, `Release_Year`,
`Concentration`, `Rating_Value`, `Rating_Count`, `Main_Accords`, `Top_Notes`,
`Middle_Notes`, `Base_Notes`, `Perfumers`.

**`FIG.csv`** (9 cols): `CAS number`, `Principal name`, `Primary descriptor`,
`Descriptor 2`, `Descriptor 3`, `Priority Date`, `Grant Date`,
`Publication Number`.

## Notes

- The three perfume databases (Fragrantica, Aromo, Parfumo) are community-
  contributed and were scraped for research use; they are provided here for
  reproducibility of the analyses only.
- Years, ratings, and vote counts are self-reported by each site's users and
  can be missing or noisy; the notebooks apply their own quality filters
  (e.g. `Total_votes >= 286`).
