# PhishGuard

PhishGuard is a hybrid machine-learning and rules-based phishing email detector. It loads or generates a dataset, engineers rich textual and heuristic features, trains multiple models, and provides CLI tools for training, evaluation, and prediction with explanations.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If `./data/emails.csv` is missing, the training command automatically creates a synthetic dataset so the project works end-to-end.

## Make targets

| Command | Description |
|---------|-------------|
| `make setup` | Create virtual environment and install dependencies |
| `make train` | Train the phishing detector (saves artifacts under `./artifacts`) |
| `make evaluate` | Evaluate the saved model |
| `make predict` | Run a sample prediction using the CLI |
| `make test` | Execute unit tests |
| `make lint` | Run basic formatting checks |

## CLI usage

Train and evaluate:

```bash
python -m phishguard.cli train --data ./data/emails.csv
python -m phishguard.cli evaluate --data ./data/emails.csv
```

Single prediction:

```bash
python -m phishguard.cli predict \
  --subject "Urgent payroll update" \
  --body "Please verify your account at http://bit.ly/fake" \
  --from_address "Payroll <payroll@alerts-update.com>" \
  --json
```

Predict from an `.eml` file:

```bash
python -m phishguard.cli predict-file --path ./samples/sample_email.eml
```

## Sample output

```
$ python -m phishguard.cli train --data ./data/emails.csv
[INFO] Dataset ./data/emails.csv missing. Generating synthetic data.
[INFO] Split dataset into train=72, valid=24, test=24
[INFO] Evaluating model logistic_regression via cross-validation
[INFO] Evaluating model gradient_boosting via cross-validation
[INFO] Training best model logistic_regression on train+valid set
[INFO] Saved model artifacts to artifacts
[INFO] Best model: logistic_regression
[INFO] Test metrics: accuracy=0.833 precision=0.857 recall=0.750 f1=0.800 roc_auc=0.912
[INFO] Confusion matrix:
[[18  2]
 [ 2 14]]
```

```
$ python -m phishguard.cli predict --subject "Urgent payroll update" \
    --body "Please verify your account at http://bit.ly/fake" \
    --from_address "Payroll <payroll@alerts-update.com>"
label=phishing ml_prob=0.871 rule_score=0.450 final=0.931
 - ML: text_word__tfidf__urgent (+0.731)
 - ML: text_word__tfidf__verify (+0.512)
 - Rule: credential_request (+0.25)
 - Rule: urgency_language (+0.20)
```

## Testing

```bash
make test
```

## Security considerations

* Email content is never executed; HTML is sanitized and scripts removed.
* URLs are extracted via regex only—no network access is performed.
* Inputs are validated and defaulted to safe fallbacks when missing.
