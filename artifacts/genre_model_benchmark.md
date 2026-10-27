# Genre Model Benchmark

Dataset: 10,000 books; stratified test split: 25%; random state: 42.

| Model | Accuracy | Macro-F1 |
|---|---:|---:|
| Logistic Regression | 0.9500 | 0.7866 |
| Complement Naive Bayes | 0.8472 | 0.6706 |
| Linear SVM | 0.9756 | 0.8681 |
| Random Forest | 0.9796 | 0.8732 |

## Notes

- Accuracy and macro-F1 are measured on a stratified held-out split.
- Character n-grams are used only by this offline benchmark; the live API uses word-level TF-IDF features.
- Horror and Adventure have very few examples and their per-class scores are unstable.
- The API multi-label model currently uses weak metadata-derived secondary labels; reviewed multi-label annotations are still needed for a fully supervised benchmark.

## Not run

- XGBoost (package not installed)
