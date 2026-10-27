# BookWise Genre Audit Report

Generated: 2026-10-26

## Scope

This audit covers `data/processed/books_clean.csv`. It is a read-only inventory of the current genre labels and does not change the recommender or genre-prediction model.

## Dataset summary

| Measure | Result |
|---|---:|
| Books inspected | 10,000 |
| Unique primary-genre labels | 11 |
| Missing primary-genre values | 0 |
| Largest class | Fantasy (3,458) |
| Smallest class | Adventure (3) |

## Current labels

| Current label | Books | Share | Audit note |
|---|---:|---:|---|
| Fantasy | 3,458 | 34.58% | Dominant class; likely to influence predictions strongly |
| Romance | 1,863 | 18.63% | Well represented |
| Classics | 1,390 | 13.90% | Well represented |
| Mystery & Thriller | 1,324 | 13.24% | Combined label; should remain combined until finer labels are available |
| Nonfiction | 831 | 8.31% | Broad umbrella category |
| Historical Fiction | 544 | 5.44% | Usable class |
| Science Fiction | 239 | 2.39% | Small but usable with regularization |
| General Fiction | 234 | 2.34% | Broad fallback category |
| Young Adult | 108 | 1.08% | Small class; evaluate carefully |
| Horror | 6 | 0.06% | Too small for reliable standalone training |
| Adventure | 3 | 0.03% | Too small for reliable standalone training |

## Proposed canonical taxonomy

For the next iteration, keep these as the canonical top-level labels so existing training data is not silently relabeled:

```text
Fantasy
Romance
Classics
Mystery & Thriller
Nonfiction
Historical Fiction
Science Fiction
General Fiction
Young Adult
Horror
Adventure
```

Add subgenre and keyword metadata separately instead of replacing the primary label:

| Signal examples | Suggested subgenre signal |
|---|---|
| dragons, magic, wizard, spell, kingdom | Fantasy |
| detective, murder, investigation, crime | Mystery & Thriller |
| love, relationship, marriage, attraction | Romance |
| space, alien, futuristic, spaceship | Science Fiction |
| ghosts, haunted, supernatural, terrifying | Horror |
| journey, expedition, quest, survival | Adventure |

These signals should be used as additional features or multi-label outputs, not as a replacement for the dataset's primary genre.

## Findings

1. The labels are highly imbalanced. Fantasy contains more than half of the combined counts of the next two largest classes, while Horror and Adventure have too few examples for dependable supervised predictions.
2. `Mystery & Thriller` is already a combined label. Splitting it into two classes would require better source labels or additional reviewed training examples.
3. `Nonfiction` and `General Fiction` are broad fallback labels and may reduce prediction specificity.
4. The current genre model should report confidence carefully for rare classes and should be evaluated with macro-F1, not accuracy alone.
5. A multi-label model is a better long-term fit because a book can be Fantasy and Adventure, or Romance and Historical Fiction, at the same time.

## Recommended next implementation

1. Keep the 11 canonical primary labels for compatibility.
2. Add normalized keyword aliases as secondary features.
3. Add descriptions to the training text if a reliable description field becomes available.
4. Evaluate Logistic Regression, Complement Naive Bayes, and Linear SVM using macro-F1 and per-class recall.
5. Treat Horror and Adventure as exploratory labels until more examples are available.
6. Add multi-label genre prediction after the single-label baseline is measured.

## Conclusion

The current dataset is suitable for a first supervised genre classifier, but it is not yet balanced enough to support a claim that all genres are predicted equally well. The safest next step is to preserve the current labels, add secondary genre signals, and measure per-genre performance before expanding the taxonomy.

## Runtime unknown-tag storage

Unknown tag phrases are recorded locally in `artifacts/unknown_genre_tags.json` with a normalized key and occurrence count. They are telemetry only: an unknown tag is never promoted to a genre automatically. The file is ignored by Git so local user input is not committed; a future review workflow can promote frequently observed tags into the reviewed alias map.
