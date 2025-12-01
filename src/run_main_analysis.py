import pandas as pd
import scipy.stats as stats
import statsmodels.api as sm
import numpy as np
import sys

# --- Configuration ---
INPUT_CSV = '../data/processed/complete_dataset.csv'
ALPHA = 0.05


def get_config_type(path_str):
    """Helper function to categorize config file paths."""
    if not isinstance(path_str, str):
        return 'Unknown'

    if 'eslint.config.' in path_str:
        return 'Modern (Flat)'
    else:
        return 'Legacy (.eslintrc)'


def run_analysis():
    """
    Main function to load data and run all statistical analyses for RQ1, RQ2, and RQ3.
    """
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"Error: Input file '{INPUT_CSV}' not found.")
        print("Please make sure the script is in the same directory as the CSV.")
        sys.exit(1)

    print(f"Successfully loaded '{INPUT_CSV}'. Starting analysis...\n")

    # --- Data Preparation ---
    # Create 'project_age_days'
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['project_age_days'] = (pd.Timestamp.now(tz='UTC') - df['created_at']).dt.days

    # Use log(x + 1) to handle 0 values
    df['log_age'] = np.log1p(df['project_age_days'])
    df['log_size'] = np.log1p(df['size_kb'])
    df['log_contributors'] = np.log1p(df['contributors_count'])
    df['log_stars'] = np.log1p(df['stars'])

    # Define our main groups
    no_eslint_group = df[df['has_eslint'] == False].copy()
    all_eslint_group = df[df['has_eslint'] == True].copy()
    valid_eslint_group = df[df['analysis_status'] == 'success'].copy()
    failed_eslint_group = df[df['analysis_status'] == 'failed'].copy()

    # --- Create Strictness Categories ---
    bins = [-np.inf, 0, 0.80, 0.9999, 1.0]
    labels = ['No Strictness (0%)', 'Low Strictness (1-80%)', 'High Strictness (81-99%)', 'Max Strictness (100%)']
    valid_eslint_group['strictness_category'] = pd.cut(
        valid_eslint_group['relative_strictness'],
        bins=bins,
        labels=labels,
        right=True
    )

    # --- Create Config Type Categories ---
    valid_eslint_group['config_type'] = valid_eslint_group['eslint_config_path'].apply(get_config_type)

    # --- RQ1: Prevalence and Strictness (Descriptive Statistics) ---
    print("=" * 50)
    print("RQ1: Prevalence and Strictness Analysis (All 982 Repos)")
    print("=" * 50)

    total_repos = len(df)
    has_eslint_count = len(all_eslint_group)
    no_eslint_count = len(no_eslint_group)
    print(f"Total Repositories in Sample: {total_repos}")
    print(f" - Repositories with no linter: {no_eslint_count} ({no_eslint_count / total_repos:.2%})")
    print(f" - Repositories with ESLint: {has_eslint_count} ({has_eslint_count / total_repos:.2%})")
    success_count = len(valid_eslint_group)
    failed_count = len(failed_eslint_group)
    print(f"\nBreakdown of {has_eslint_count} Repos with ESLint:")
    print(f" - Successfully Analyzed: {success_count} ({success_count / has_eslint_count:.2%})")
    print(f" - Failed to Analyze: {failed_count} ({failed_count / has_eslint_count:.2%})")
    abs_strict_desc = valid_eslint_group['absolute_strictness'].describe()
    rel_strict_desc = valid_eslint_group['relative_strictness'].describe()
    print("\nDescriptive Statistics for Valid ESLint Repos (n=" + str(success_count) + "):")
    print(f"  Absolute: Mean: {abs_strict_desc['mean']:.2f}, Median: {abs_strict_desc['50%']:.2f}")
    print(f"  Relative: Mean: {rel_strict_desc['mean'] * 100:.2f}%, Median: {rel_strict_desc['50%'] * 100:.2f}%")

    # --- RQ2: Bug-Fix Ratio Comparison (ESLint vs. No ESLint) ---
    print("\n" + "=" * 50)
    print("RQ2: Bug-Fix Ratio Comparison")
    print("=" * 50)

    # (Tests 2a, 2b, 2c, 2d )
    print("\n--- Test 2a: Valid ESLint Repos (n={}) vs. No ESLint Repos (n={}) ---".format(len(valid_eslint_group),
                                                                                           len(no_eslint_group)))
    group1_data = no_eslint_group['bug_fix_ratio'].dropna()
    group2_data = valid_eslint_group['bug_fix_ratio'].dropna()
    test_stat, p_value = stats.mannwhitneyu(group1_data, group2_data, alternative='two-sided')
    print(f"  Test Used: Mann-Whitney U Test, P-value: {p_value:.4g}")
    print(f"  Mean Bug-Fix Ratio (No ESLint): {group1_data.mean():.4f}, (Valid ESLint): {group2_data.mean():.4f}")

    print("\n--- Test 2b: All ESLint Repos (n={}) vs. No ESLint Repos (n={}) ---".format(len(all_eslint_group),
                                                                                         len(no_eslint_group)))
    group_all_eslint_data = all_eslint_group['bug_fix_ratio'].dropna()
    test_stat, p_value = stats.mannwhitneyu(group1_data, group_all_eslint_data, alternative='two-sided')
    print(f"  Test Used: Mann-Whitney U Test, P-value: {p_value:.4g}")
    print(
        f"  Mean Bug-Fix Ratio (No ESLint): {group1_data.mean():.4f}, (All ESLint): {group_all_eslint_data.mean():.4f}")
    if p_value < ALPHA:
        print(f"  Result: The difference is statistically significant (p < {ALPHA}).")
    else:
        print(f"  Result: The difference is not statistically significant (p >= {ALPHA}).")

    print("\n--- Test 2c: Bug-Fix Ratio by Strictness Category (Kruskal-Wallis Test) ---")
    g_no_eslint = no_eslint_group['bug_fix_ratio'].dropna()
    g_no_strict = valid_eslint_group[valid_eslint_group['strictness_category'] == 'No Strictness (0%)'][
        'bug_fix_ratio'].dropna()
    g_low_strict = valid_eslint_group[valid_eslint_group['strictness_category'] == 'Low Strictness (1-80%)'][
        'bug_fix_ratio'].dropna()
    g_high_strict = valid_eslint_group[valid_eslint_group['strictness_category'] == 'High Strictness (81-99%)'][
        'bug_fix_ratio'].dropna()
    g_max_strict = valid_eslint_group[valid_eslint_group['strictness_category'] == 'Max Strictness (100%)'][
        'bug_fix_ratio'].dropna()
    groups = [g_no_eslint, g_no_strict, g_low_strict, g_high_strict, g_max_strict]
    group_labels = ['No ESLint', 'No Strictness (0%)', 'Low Strictness (1-80%)', 'High Strictness (81-99%)',
                    'Max Strictness (100%)']
    valid_groups = [g for g in groups if len(g) > 0]
    valid_labels = [group_labels[i] for i, g in enumerate(groups) if len(g) > 0]
    print(f"Comparing {len(valid_groups)} groups:")
    for i, label in enumerate(valid_labels): print(
        f"  - {label} (n={len(valid_groups[i])}), Median Bug-Fix Ratio: {valid_groups[i].median():.4f}")
    h_stat, p_value = stats.kruskal(*valid_groups)
    print(f"  Kruskal-Wallis Test P-value: {p_value:.4g}")

    print("\n--- Test 2d: Bug-Fix Ratio by Analysis Status (Kruskal-Wallis Test) ---")
    g_no_eslint_data = no_eslint_group['bug_fix_ratio'].dropna()
    g_valid_eslint_data = valid_eslint_group['bug_fix_ratio'].dropna()
    g_failed_eslint_data = failed_eslint_group['bug_fix_ratio'].dropna()
    print("Comparing 3 groups:")
    print(f"  - No ESLint (n={len(g_no_eslint_data)}), Median Bug-Fix Ratio: {g_no_eslint_data.median():.4f}")
    print(f"  - Valid ESLint (n={len(g_valid_eslint_data)}), Median Bug-Fix Ratio: {g_valid_eslint_data.median():.4f}")
    print(
        f"  - Failed ESLint (n={len(g_failed_eslint_data)}), Median Bug-Fix Ratio: {g_failed_eslint_data.median():.4f}")
    h_stat, p_value = stats.kruskal(g_no_eslint_data, g_valid_eslint_data, g_failed_eslint_data)
    print(f"  Kruskal-Wallis Test P-value: {p_value:.4g}")

    # --- Test 2e: Analysis of Confounding Variables ---
    print("\n--- Test 2e: Analysis of Confounding Variables (Explaining Test 2b) ---")
    print("Comparing control variables between 'No ESLint' and 'All ESLint' groups")

    vars_to_check = ['project_age_days', 'contributors_count', 'stars', 'size_kb']
    for var in vars_to_check:
        g1 = no_eslint_group[var].dropna()
        g_all = all_eslint_group[var].dropna()

        # Test for significance
        u_stat, p_value = stats.mannwhitneyu(g1, g_all, alternative='two-sided')

        print(f"\n  Variable: {var}")
        print(f"    Median (No ESLint): {g1.median():.2f}")
        print(f"    Median (All ESLint): {g_all.median():.2f}")
        print(f"    Mann-Whitney U Test P-value: {p_value:.4g}")
        if p_value < ALPHA:
            print(f"    Result: 'All ESLint' group is *significantly different*.")
        else:
            print(f"    Result: No significant difference.")

    # --- Test 2f: Bug-Fix Ratio by Config Type ---
    print("\n--- Test 2f: Bug-Fix Ratio by Config Type (Kruskal-Wallis Test) ---")

    g_legacy_config = valid_eslint_group[valid_eslint_group['config_type'] == 'Legacy (.eslintrc)'][
        'bug_fix_ratio'].dropna()
    g_modern_config = valid_eslint_group[valid_eslint_group['config_type'] == 'Modern (Flat)']['bug_fix_ratio'].dropna()

    print("Comparing 3 groups:")
    print(f"  - No ESLint (n={len(g_no_eslint_data)}), Median Bug-Fix Ratio: {g_no_eslint_data.median():.4f}")
    print(f"  - Legacy Config (n={len(g_legacy_config)}), Median Bug-Fix Ratio: {g_legacy_config.median():.4f}")
    print(f"  - Modern Config (n={len(g_modern_config)}), Median Bug-Fix Ratio: {g_modern_config.median():.4f}")

    h_stat, p_value = stats.kruskal(g_no_eslint_data, g_legacy_config, g_modern_config)
    print(f"\nKruskal-Wallis Test Statistic: {h_stat:.4f}, P-value: {p_value:.4g}")
    if p_value < ALPHA:
        print(f"  Result: A statistically significant difference exists between at least two of the groups.")
    else:
        print(f"  Result: No statistically significant difference was found between the groups.")

    # --- RQ3: Strictness Correlation & Regression ---
    print("\n" + "=" * 50)
    print("RQ3: Strictness Correlation and Regression")
    print("=" * 50)

    # 3a. Correlation (Spearman)
    print("\nStep 3a: Correlation (Strictness vs. Bug-Fix Ratio)")
    print("Using Spearman correlation (data is not normal).")
    corr_abs, p_abs = stats.spearmanr(valid_eslint_group['absolute_strictness'], valid_eslint_group['bug_fix_ratio'])
    corr_rel, p_rel = stats.spearmanr(valid_eslint_group['relative_strictness'], valid_eslint_group['bug_fix_ratio'])
    print(f"  Absolute Strictness vs. Bug-Fix Ratio: Corr={corr_abs:.4f}, p-value={p_abs:.4g}")
    print(f"  Relative Strictness vs. Bug-Fix Ratio: Corr={corr_rel:.4f}, p-value={p_rel:.4g}")

    # 3b. Multiple Linear Regression (Using Categories)
    # (We keep this as a reference to what we did before)
    print("\nStep 3b: Multiple Linear Regression Model (Original Model)")
    eslint_data = valid_eslint_group.copy()
    Y = eslint_data['bug_fix_ratio']
    X_base = df.loc[eslint_data.index][['project_age_days', 'size_kb', 'contributors_count', 'stars']]
    X_dummies = pd.get_dummies(eslint_data['strictness_category'], prefix='strictness', drop_first=True, dtype=int)
    X = pd.concat([X_base, X_dummies], axis=1)
    X = sm.add_constant(X, has_constant='add')
    final_data = pd.concat([Y, X], axis=1).dropna()
    Y_final = final_data['bug_fix_ratio']
    X_final = final_data.drop('bug_fix_ratio', axis=1)
    X_final = X_final.apply(pd.to_numeric, errors='coerce')
    final_data_numeric = pd.concat([Y_final, X_final], axis=1).dropna()
    Y_final = final_data_numeric['bug_fix_ratio']
    X_final = final_data_numeric.drop('bug_fix_ratio', axis=1)
    print(f"\nRunning regression on {len(X_final)} observations (Full Model).")
    model_full = sm.OLS(Y_final, X_final).fit()
    print(model_full.summary())

    # --- Test 3d: Strictness by Config Type ---
    print("\n--- Test 3d: Strictness by Config Type (Mann-Whitney U Test) ---")
    print("Comparing 'Relative Strictness' between Legacy and Modern configs")

    # We re-use the groups from Test 2f
    g_legacy_strictness = valid_eslint_group[valid_eslint_group['config_type'] == 'Legacy (.eslintrc)'][
        'relative_strictness'].dropna()
    g_modern_strictness = valid_eslint_group[valid_eslint_group['config_type'] == 'Modern (Flat)'][
        'relative_strictness'].dropna()

    print(
        f"  Median Relative Strictness (Legacy, n={len(g_legacy_strictness)}): {g_legacy_strictness.median() * 100:.2f}%")
    print(
        f"  Median Relative Strictness (Modern, n={len(g_modern_strictness)}): {g_modern_strictness.median() * 100:.2f}%")

    u_stat, p_value = stats.mannwhitneyu(g_legacy_strictness, g_modern_strictness, alternative='two-sided')
    print(f"\nMann-Whitney U Test Statistic: {u_stat:.4f}, P-value: {p_value:.4g}")
    if p_value < ALPHA:
        print(f"  Result: A statistically significant difference in strictness exists.")
    else:
        print(f"  Result: No statistically significant difference in strictness found.")

    # --- Test 3e: Log-Transformed Regression Model ---
    print("\n--- Test 3e: Log-Transformed Linear Regression Model (To Fix Multicollinearity) ---")

    # Prep data: use the valid_eslint_group
    eslint_data = valid_eslint_group.copy()

    # 1. Define Y (Dependent Variable)
    Y = eslint_data['bug_fix_ratio']

    # 2. Define X (Independent Variables)
    X_base = df.loc[eslint_data.index][['log_age', 'log_size', 'log_contributors', 'log_stars']]

    # Create dummy variables for the categories
    X_dummies = pd.get_dummies(eslint_data['strictness_category'], prefix='strictness', drop_first=True, dtype=int)

    # Combine base variables and dummy variables
    X = pd.concat([X_base, X_dummies], axis=1)

    # 3. Add constant (intercept)
    X = sm.add_constant(X, has_constant='add')

    # 4. Drop any rows with NaNs (regression can't handle them)
    final_data = pd.concat([Y, X], axis=1).dropna()
    Y_final = final_data['bug_fix_ratio']
    X_final = final_data.drop('bug_fix_ratio', axis=1)

    # 5. Apply numeric conversion (as a safeguard)
    Y_final = pd.to_numeric(Y_final, errors='coerce')
    X_final = X_final.apply(pd.to_numeric, errors='coerce')
    final_data_numeric = pd.concat([Y_final, X_final], axis=1).dropna()
    Y_final = final_data_numeric['bug_fix_ratio']
    X_final = final_data_numeric.drop('bug_fix_ratio', axis=1)

    print(f"\nRunning regression on {len(X_final)} observations (Log-Transformed Model).")

    # 6. Fit the OLS (Ordinary Least Squares) model
    model_log = sm.OLS(Y_final, X_final).fit()

    # 7. Print the full summary
    print(model_log.summary())

    print("\n--- Analysis Complete ---")

if __name__ == "__main__":
    run_analysis()