# An Empirical Study on the Efficacy of ESLint in Reducing Bugs in TypeScript

**CMPT 479/982 Project**

This repository contains the data collection and analysis scripts for the research project: **"An Empirical Study on the Efficacy of ESLint in Reducing Bugs in TypeScript."**

The goal of this research is to empirically study the relationship between ESLint adoption, configuration strictness, and bug-fix activity in open-source TypeScript projects.

## 🚀 Project Goals

This project seeks to answer the following research questions:

* **RQ1:** How prevalent is the adoption of ESLint among open-source TypeScript Projects, and how strict are their configurations?
* **RQ2:** Do TypeScript projects that use ESLint exhibit lower bug-fix ratios compared to those that do not?
* **RQ3:** Is there a relationship between the strictness of a project's ESLint configuration and its bug-fix activity?
* **RQ4:** For a subset of bug-fix commits, what fraction are "linter-preventable" under a project's actual config vs. a standard config?

---

## 📂 Dataset Location

The final, processed dataset used for all statistical analysis is located at:

`data/processed/complete_dataset.csv`

This file combines repository metadata, ESLint strictness metrics, bug-fix ratios, and testing culture metrics into a single resource.

---

## 🛠️ Methodology & Script Guide

The analysis pipeline is located in the `src/` directory.

### 1. Data Collection
* **`collect_repos.py`**: Queries the GitHub REST API to find active, non-forked TypeScript repositories with >50 stars. It detects if an ESLint config exists (legacy or flat config) and saves the initial metadata.
* **`create_file_validation_sample.py`**: Generates a random sample of repositories to manually verify that our "has ESLint" detection logic is accurate.

### 2. Strictness Analysis
* **`calculate_strictness.py`**: The core analysis script. It clones each repository, runs `npm install`, and calls the **ESLint Helper** to calculate the Absolute Strictness and Relative Strictness scores.
* **`save_all_configs.py`**: A utility script that saves the full, flattened JSON configuration for each repository into the `eslint_configs/` directory for inspection.

### 3. Quality Analysis (Bug-Fix Ratio & RQ4)
* **`get_commits.py`**: Uses the GitHub API to count the total number of commits and the number of "bug-fix" commits (using keyword matching) to calculate the Bug-Fix Ratio.
* **`get_commits_for_manual_checkout.py`**: Clones repositories and uses `git log` to extract specific bug-fix commits from projects with ESLint for the qualitative deep dive (RQ4).
* **`get_commits_for_manual_analysis_noESLint.py`**: A counterpart script that extracts bug-fix commits from projects without ESLint for manual comparison.

### 4. Testing Culture Analysis
* **`get_testing_data.py`**: Scans repositories to determine if they have a test suite. It calculates the **Test Code Ratio** (percentage of code that is test code) and identifies the testing framework used (e.g., Jest, Mocha).

### 5. Statistical Analysis & Visualization
* **`run_main_analysis.py`**: Runs the complete suite of statistical tests (Mann-Whitney U, Kruskal-Wallis, Spearman Correlation, and OLS Regression) for RQ1, RQ2, and RQ3.
* **`analyze_testing_and_create_visualizations.py`**: Runs the interaction analysis (Testing * Strictness) and generates all the plots and figures used in the final report.
* **`create_main_visualizations.py`**: Generates the primary visualizations for the initial research questions.

---

## 🧩 The ESLint Helper & Standard Linter

Located in `eslint-helper/`, this is a critical component of our strictness analysis.

**Why it exists:**
We cannot simply parse an `.eslintrc.json` file because most modern projects use `extends` (e.g., `extends: ['airbnb', 'standard']`). To know the actual rules, we must resolve these dependencies.

**How it works:**
1.  The Python script (`calculate_strictness.py`) clones a repo and runs `npm install`.
2.  It calls the Node.js script `eslint-helper/get_config.js`.
3.  `get_config.js` uses ESLint's internal Node.js API (`calculateConfigForFile`) to load the project's specific ESLint configuration, resolving all plugins and extended presets.
4.  It returns the final, flattened configuration object to Python.
5.  Python counts the number of rules set to "error" vs "warn" to calculate strictness.

Located in `standard_linter/`, the `eslint.config.js` is the ESLint configuration file used in the Deep Dive Analysis for RQ4. It utilizes the official `typescript-eslint` strict and stylistic options. This provides an unbiased and maximum strictness baseline to determine if a bug was theoritetically preventable by any modern static analysis rule, regardless of the rules the project owners chose to enable. 

---

## ⚙️ Setup and Installation

### 1. System Dependencies
* Python 3.8+
* Node.js v18+ (which includes npm)
* Git

### 2. Python Dependencies
It is highly recommended to use a virtual environment.

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install required Python packages
pip install pandas requests scipy statsmodels matplotlib seaborn tqdm
```

### 3. Node.js Helper Dependencies
You must install the dependencies for the helper script before running the analysis

```bash
cd eslint-helper
npm install
cd ..
```

### 4. GitHub Access Token
The data collection scripts require a GitHub Personal Access Token to use the API

1.  Generate a new "classic" token.
2.  Give it the `public_repo` scope.
3.  Set the token as an environment variable:

## 🔬 Reproduciblity Order

To reproduce the comeplte dataset from scratch and the visualizations, run the scripts in this order

1. `src/collect_repos.py` 
2. `src/calculate_strictness.py`
3. `src/get_commits.py`
4. `src/get_testing_data.py`
5. `sec/run_main_analysis.py`
6. `src/analyze_testing_and_create_visualizations`
7. `src/create_main_visulizations`

* Note: Adjust paths accordingly for all scripts depending on where input and output files are located / will be saved. 
* Note: Our complete dataset originates from a random sample from the GITHUB API. The exact data optained may be different. If you wish to get our results, you may direclty use the complete_dataset.csv and skip all data collection scripts. 

