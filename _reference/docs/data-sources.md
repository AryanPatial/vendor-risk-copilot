# Where the data comes from

Everything below is public and free. Nothing here needs an employer or an NDA.

## 1. The answer bank — completed CAIQ responses

The CSA **STAR Registry** is a public list of cloud providers who have filled in the CAIQ
questionnaire and published their answers. Each entry is a spreadsheet of real
question-and-answer pairs written by a real security team.

- https://cloudsecurityalliance.org/star

Pick one provider and treat it as the company you work for. Download their completed CAIQ and
ingest it:

```bash
qre ingest answers data/raw/<provider>_caiq.xlsx --company <slug>
```

Ingest a second, older submission from the same provider if one exists — that gives the answer
bank overlapping entries, which is what a real one looks like.

## 2. Incoming questionnaires

These are the blank question sets a customer would send.

| Source | Notes |
|---|---|
| [CAIQ (CSA)](https://cloudsecurityalliance.org/artifacts/consensus-assessments-initiative-questionnaire-v3-1) | Free. ~260 questions. |
| [HECVAT (EDUCAUSE)](https://www.educause.edu/higher-education-community-vendor-assessment-toolkit) | Free, Excel, v4.1.5. Used by universities. |
| [HECVAT (REN-ISAC)](https://ren-isac.net/hecvat/index.html) | Mirror, plus older versions. |

HECVAT is the better test input: it asks for the same information as CAIQ but words it
differently, which is exactly the case the retriever has to handle.

SIG / SIG Lite is the other common questionnaire, but it needs a paid licence from Shared
Assessments. Skip it.

## 3. Policy documents

Grounding answers only in past answers is fragile. Policy documents give the system a second
source that says what the company actually commits to.

| Source | Notes |
|---|---|
| [strongdm/comply](https://github.com/strongdm/comply) | 24 SOC 2 policies in markdown. Drop straight into `data/raw/policies/`. |
| [JupiterOne/security-policy-templates](https://github.com/JupiterOne/security-policy-templates) | Policies and control procedures mapped to SOC 2, NIST CSF, PCI DSS. |

```bash
qre ingest policies data/raw/policies --company <slug>
```

## Building the evaluation set

Once the answer bank is loaded:

```bash
qre eval build --company <slug> --size 50
qre eval run --company <slug>
```

`eval build` samples 50 answered questions, rewrites each one so the wording differs from what is
stored, and adds a few questions the corpus cannot answer. `eval run` then reports whether each
configuration still retrieves the original entry, and whether low-evidence questions are correctly
flagged for a human.

The rewriting step is the only part that costs money, and it runs once. Keep the generated
`data/eval/<slug>.jsonl` under version control so results stay comparable between runs.
