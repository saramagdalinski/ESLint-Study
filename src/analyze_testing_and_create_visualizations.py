import pandas as pd
import scipy.stats as stats
import statsmodels.api as sm
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import os
import sys

# --- Configuration ---
INPUT_CSV = '../data/processed/complete_dataset.csv'
SAVE_DIR = '../visualizations_testing'
ALPHA = 0.05


def run_testing_analysis():
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"Error: Input file '{INPUT_CSV}' not found.")
        sys.exit(1)

    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    print(f"Successfully loaded '{INPUT_CSV}'. Starting Testing Analysis...\n")

    # --- Data Cleaning & Prep ---
    # Ensure relevant columns are numeric
    cols_to_clean = ['test_code_ratio', 'bug_fix_ratio', 'relative_strictness',
                     'project_age_days', 'size_kb', 'contributors_count', 'stars']

    # Recalculate project age if missing, assuming 'created_at' exists
    if 'created_at' in df.columns and 'project_age_days' not in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at'])
        df['project_age_days'] = (pd.Timestamp.now(tz='UTC') - df['created_at']).dt.days

    for col in cols_to_clean:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Create log-transformed controls
    df['log_age'] = np.log1p(df['project_age_days'])
    df['log_contributors'] = np.log1p(df['contributors_count'])
    df['log_size'] = np.log1p(df['size_kb'])
    df['log_stars'] = np.log1p(df['stars'])

    # Define Groups
    no_eslint = df[df['has_eslint'] == False].dropna(subset=['test_code_ratio'])
    valid_eslint = df[df['analysis_status'] == 'success'].dropna(subset=['test_code_ratio', 'relative_strictness'])
    # --- ADDED: All ESLint group for prevalence calc ---
    all_eslint = df[df['has_eslint'] == True]

    print(f"Data Points for Analysis: No ESLint (n={len(no_eslint)}), Valid ESLint (n={len(valid_eslint)})")

    # --- Analysis 0: Prevalence of Tests (ESLint vs No ESLint) ---
    print("\n" + "=" * 50)
    print("0. Prevalence of Tests (ESLint vs No ESLint)")
    print("=" * 50)

    # No ESLint stats
    no_eslint_total = len(no_eslint)
    no_eslint_with_tests = len(no_eslint[no_eslint['has_tests'] == True])
    no_eslint_pct = (no_eslint_with_tests / no_eslint_total * 100) if no_eslint_total > 0 else 0

    # ESLint stats (using ALL ESLint repos, not just valid ones)
    all_eslint_total = len(all_eslint)
    all_eslint_with_tests = len(all_eslint[all_eslint['has_tests'] == True])
    all_eslint_pct = (all_eslint_with_tests / all_eslint_total * 100) if all_eslint_total > 0 else 0

    print(f"No ESLint Repos (n={no_eslint_total}):")
    print(f"  With Tests: {no_eslint_with_tests} ({no_eslint_pct:.2f}%)")

    print(f"All ESLint Repos (n={all_eslint_total}):")
    print(f"  With Tests: {all_eslint_with_tests} ({all_eslint_pct:.2f}%)")

    # --- Analysis 1: Does Linting Correlate with Testing? ---
    print("\n" + "=" * 50)
    print("1. Linting vs. Testing Culture")
    print("=" * 50)

    median_no = no_eslint['test_code_ratio'].median()
    median_valid = valid_eslint['test_code_ratio'].median()

    u_stat, p_val = stats.mannwhitneyu(no_eslint['test_code_ratio'], valid_eslint['test_code_ratio'],
                                       alternative='two-sided')

    print(f"Median Test Code Ratio (No ESLint): {median_no:.4f}")
    print(f"Median Test Code Ratio (Valid ESLint): {median_valid:.4f}")
    print(f"Mann-Whitney U p-value: {p_val:.4g}")

    if p_val < ALPHA:
        print("Result: Significant difference. Projects with ESLint test more/less.")
    else:
        print("Result: No significant difference in testing culture.")

    # Viz 1
    plt.figure(figsize=(8, 6))
    plot_data = pd.concat([no_eslint.assign(Group='No ESLint'), valid_eslint.assign(Group='Valid ESLint')])
    sns.boxplot(x='Group', y='test_code_ratio', data=plot_data, palette="pastel", showfliers=False)
    plt.title('Test Code Ratio by ESLint Status')
    plt.savefig(os.path.join(SAVE_DIR, '01_testing_culture_boxplot.png'))
    plt.close()

    # --- Analysis 4: Baseline - Does Testing Reduce Bugs? ---
    # (Doing this before regression to establish a baseline)
    print("\n" + "=" * 50)
    print("2. Baseline: Does Testing Reduce Bugs?")
    print("=" * 50)

    # Use the whole dataset for maximum power
    all_data = df.dropna(subset=['test_code_ratio', 'bug_fix_ratio'])
    corr, p_val = stats.spearmanr(all_data['test_code_ratio'], all_data['bug_fix_ratio'])

    print(f"Spearman Correlation (Test Ratio vs. Bug Ratio): {corr:.4f}")
    print(f"P-value: {p_val:.4g}")

    # Viz 2
    plt.figure(figsize=(10, 6))
    sns.regplot(x='test_code_ratio', y='bug_fix_ratio', data=all_data,
                scatter_kws={'alpha': 0.3}, line_kws={'color': 'red'})
    plt.title('Bug-Fix Ratio vs. Test Code Ratio (All Repos)')
    plt.ylim(0, 0.5)  # Zoom in
    plt.savefig(os.path.join(SAVE_DIR, '02_testing_vs_bugs_scatter.png'))
    plt.close()

    # --- Analysis 2: Regression with Interaction (Linting * Testing) ---
    print("\n" + "=" * 50)
    print("3. Interaction Effect (Strictness * Testing)")
    print("=" * 50)

    # Use only Valid ESLint group
    reg_data = valid_eslint.copy()

    # Create Interaction Term
    reg_data['strictness_x_testing'] = reg_data['relative_strictness'] * reg_data['test_code_ratio']

    Y = reg_data['bug_fix_ratio']
    # Independent variables: Controls + Strictness + Testing + Interaction
    X = reg_data[['relative_strictness', 'test_code_ratio', 'strictness_x_testing',
                  'log_age', 'log_contributors', 'log_stars']]

    X = sm.add_constant(X)

    # Drop NaNs
    clean_data = pd.concat([Y, X], axis=1).dropna()
    Y = clean_data['bug_fix_ratio']
    X = clean_data.drop('bug_fix_ratio', axis=1)

    model = sm.OLS(Y, X).fit()
    print(model.summary())

    # Viz 3: Coefficient Plot for this model
    coef_df = pd.DataFrame({
        'param': model.params.index, 'coef': model.params.values,
        'conf_low': model.conf_int()[0], 'conf_high': model.conf_int()[1]
    }).iloc[1:]  # Skip const

    plt.figure(figsize=(10, 6))
    plt.errorbar(coef_df['coef'], coef_df['param'],
                 xerr=[coef_df['coef'] - coef_df['conf_low'], coef_df['conf_high'] - coef_df['coef']],
                 fmt='o', color='blue', ecolor='red', capsize=5)
    plt.axvline(x=0, color='black', linestyle='--')
    plt.title('Regression Coefficients: Interaction Model')
    plt.tight_layout()
    plt.savefig(os.path.join(SAVE_DIR, '03_interaction_coefficients.png'))
    plt.close()

    # --- Analysis 3: Segmented Analysis (High vs Low Testing) ---
    print("\n" + "=" * 50)
    print("4. Segmented Analysis: Strictness Effect in High vs Low Testing Groups")
    print("=" * 50)

    median_test_ratio = valid_eslint['test_code_ratio'].median()
    print(f"Median Split Threshold: {median_test_ratio:.4f}")

    low_testing = valid_eslint[valid_eslint['test_code_ratio'] <= median_test_ratio]
    high_testing = valid_eslint[valid_eslint['test_code_ratio'] > median_test_ratio]

    corr_low, p_low = stats.spearmanr(low_testing['relative_strictness'], low_testing['bug_fix_ratio'])
    corr_high, p_high = stats.spearmanr(high_testing['relative_strictness'], high_testing['bug_fix_ratio'])

    print(f"\nLow Testing Group (n={len(low_testing)}):")
    print(f"  Strictness Correlation: {corr_low:.4f}, p-value: {p_low:.4g}")

    print(f"\nHigh Testing Group (n={len(high_testing)}):")
    print(f"  Strictness Correlation: {corr_high:.4f}, p-value: {p_high:.4g}")

    print("\n--- Analysis Complete ---")


if __name__ == "__main__":
    run_testing_analysis()