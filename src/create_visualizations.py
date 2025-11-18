import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
import sys
import statsmodels.api as sm

# --- Configuration ---
INPUT_CSV = '../data/processed/repos_with_bug_fix_ratios.csv'
SAVE_DIR = 'visualizations'
ALPHA = 0.05


def get_config_type(path_str):
    """Helper function to categorize config file paths."""
    if not isinstance(path_str, str):
        return 'Unknown'
    if 'eslint.config.' in path_str:
        return 'Modern (Flat)'
    elif '.eslintrc' in path_str:
        return 'Legacy (.eslintrc)'
    else:
        return 'Unknown'


def create_visualizations():
    """
    Loads the final dataset and generates all plots for the report.
    """
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"Error: Input file '{INPUT_CSV}' not found.")
        print("Please make sure the script is in the same directory as the CSV.")
        sys.exit(1)

    # Create the directory to save plots
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    print(f"Successfully loaded '{INPUT_CSV}'. Starting visualization...\n")

    # --- Data Preparation (Mirrors run_analysis.py) ---

    # Create 'project_age_days'
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['project_age_days'] = (pd.Timestamp.now(tz='UTC') - df['created_at']).dt.days

    # Create Log-Transformed Variables
    df['log_age'] = np.log1p(df['project_age_days'])
    df['log_size'] = np.log1p(df['size_kb'])
    df['log_contributors'] = np.log1p(df['contributors_count'])
    df['log_stars'] = np.log1p(df['stars'])

    # Define main groups
    no_eslint_group = df[df['has_eslint'] == False].copy()
    valid_eslint_group = df[df['analysis_status'] == 'success'].copy()
    failed_eslint_group = df[df['analysis_status'] == 'failed'].copy()
    all_eslint_group = df[df['has_eslint'] == True].copy()

    # Create Strictness Categories
    bins = [-np.inf, 0, 0.80, 0.9999, 1.0]
    labels = ['No Strictness (0%)', 'Low Strictness (1-80%)', 'High Strictness (81-99%)', 'Max Strictness (100%)']
    valid_eslint_group['strictness_category'] = pd.cut(
        valid_eslint_group['relative_strictness'],
        bins=bins,
        labels=labels,
        right=True
    )

    # Create Config Type Categories
    valid_eslint_group['config_type'] = valid_eslint_group['eslint_config_path'].apply(get_config_type)

    # Set plot style
    sns.set_theme(style="whitegrid")

    # --- Plot 1: RQ1 - ESLint Adoption Prevalence (Pie Chart) ---
    print("Generating Plot 1: RQ1 - ESLint Adoption Prevalence...")
    plt.figure(figsize=(8, 8))
    adoption_counts = df['has_eslint'].value_counts()
    adoption_labels = {
        True: f'Have ESLint File (n={adoption_counts[True]})',
        False: f'No Linter (n={adoption_counts[False]})'
    }
    plt.pie(adoption_counts,
            labels=[adoption_labels[k] for k in adoption_counts.index],
            autopct='%1.1f%%',
            startangle=140,
            colors=sns.color_palette("pastel"))
    plt.title('RQ1: ESLint Adoption Prevalence in Sample (n=982)', fontsize=16)
    plt.savefig(os.path.join(SAVE_DIR, '01_rq1_adoption_pie_chart.png'))
    plt.close()

    # --- Plot 2: RQ1 - Analyzability of ESLint Configs (Bar Chart) ---
    print("Generating Plot 2: RQ1 - ESLint Analyzability...")
    plt.figure(figsize=(8, 6))
    funnel_df = pd.DataFrame({
        'Status': ['Analyzable (n=282)', 'Un-analyzable (n=426)'],
        'Count': [len(valid_eslint_group), len(failed_eslint_group)]
    })

    sns.barplot(x='Status', y='Count', data=funnel_df, palette="muted")
    plt.title('RQ1: Analyzability of Repos with ESLint (n=708)', fontsize=16)
    plt.ylabel('Number of Repositories')
    plt.xlabel('Configuration Status')
    plt.savefig(os.path.join(SAVE_DIR, '02_rq1_analyzability_bar_chart.png'))
    plt.close()

    # --- Plot 3: RQ1 - Distribution of Relative Strictness (Histogram) ---
    print("Generating Plot 3: RQ1 - Relative Strictness Distribution...")
    plt.figure(figsize=(10, 6))
    sns.histplot(valid_eslint_group['relative_strictness'] * 100,
                 kde=True,
                 bins=20,
                 color=sns.color_palette("deep")[2])
    plt.title('RQ1: Distribution of Relative Strictness (n=282 Valid Configs)', fontsize=16)
    plt.xlabel('Relative Strictness (% of enabled rules set to "error")')
    plt.ylabel('Number of Repositories')
    plt.savefig(os.path.join(SAVE_DIR, '03_rq1_strictness_histogram.png'))
    plt.close()

    # --- Plot 4: RQ2 - Bug-Fix Ratio by Group (Box Plot) ---
    print("Generating Plot 4: RQ2 - Bug-Fix Ratio by Group (Test 2d)...")
    no_eslint_group['group_status'] = 'No ESLint'
    valid_eslint_group['group_status'] = 'Valid ESLint'
    failed_eslint_group['group_status'] = 'Failed ESLint'

    plot_df_2d = pd.concat([no_eslint_group, valid_eslint_group, failed_eslint_group])

    plt.figure(figsize=(10, 7))
    sns.boxplot(x='group_status', y='bug_fix_ratio', data=plot_df_2d,
                palette="pastel",
                showfliers=False)  # Hide outliers
    plt.title('RQ2 (Test 2d): Bug-Fix Ratio by ESLint Analysis Status', fontsize=16)
    plt.xlabel('Project Group')
    plt.ylabel('Bug-Fix Ratio')
    plt.ylim(0, 0.5)
    plt.savefig(os.path.join(SAVE_DIR, '04_rq2_bug_ratio_by_status_boxplot.png'))
    plt.close()

    # --- Plot 5: RQ3 - Strictness vs. Bug-Fix Ratio (Scatter Plot) ---
    print("Generating Plot 5: RQ3 - Strictness vs. Bug-Fix Ratio (Test 3a)...")
    plt.figure(figsize=(10, 6))
    sns.regplot(x=valid_eslint_group['relative_strictness'] * 100,
                y=valid_eslint_group['bug_fix_ratio'],
                ci=95,
                line_kws={'color': 'red', 'linestyle': '--'},
                scatter_kws={'alpha': 0.3})
    plt.title('RQ3 (Test 3a): Bug-Fix Ratio vs. Relative Strictness', fontsize=16)
    plt.xlabel('Relative Strictness (%)')
    plt.ylabel('Bug-Fix Ratio')
    plt.savefig(os.path.join(SAVE_DIR, '05_rq3_strictness_scatter.png'))
    plt.close()

    # --- Plot 6 & 7: RQ3 - Confounding Variables (Scatter Plots) ---
    print("Generating Plot 6 & 7: RQ3 - Confounding Variables...")
    plt.figure(figsize=(10, 6))
    sns.regplot(x='project_age_days', y='bug_fix_ratio', data=df.dropna(subset=['project_age_days']),
                line_kws={'color': 'red', 'linestyle': '--'},
                scatter_kws={'alpha': 0.2})
    plt.title('RQ3: Bug-Fix Ratio vs. Project Age (All Repos)', fontsize=16)
    plt.xlabel('Project Age (Days)')
    plt.ylabel('Bug-Fix Ratio')
    plt.savefig(os.path.join(SAVE_DIR, '06_rq3_age_scatter.png'))
    plt.close()

    plt.figure(figsize=(10, 6))
    sns.regplot(x='contributors_count', y='bug_fix_ratio', data=df.dropna(subset=['contributors_count']),
                line_kws={'color': 'red', 'linestyle': '--'},
                scatter_kws={'alpha': 0.2})
    plt.title('RQ3: Bug-Fix Ratio vs. Contributors (All Repos)', fontsize=16)
    plt.xlabel('Number of Contributors (Log Scale)')
    plt.ylabel('Bug-Fix Ratio')
    plt.xscale('log')
    plt.savefig(os.path.join(SAVE_DIR, '07_rq3_contributors_scatter.png'))
    plt.close()

    # --- NEW Plot 8: Test 2e - Confounding Variables Boxplots ---
    print("Generating Plot 8: RQ2 (Test 2e) - Confounding Variables...")
    df['group_2b'] = np.where(df['has_eslint'] == True, 'All ESLint', 'No ESLint')
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('RQ2 (Test 2e): "ESLint Paradox" - Confounding Variables', fontsize=20, y=1.03)

    sns.boxplot(ax=axes[0, 0], x='group_2b', y='contributors_count', data=df, palette="pastel", showfliers=False)
    axes[0, 0].set_title('Contributors Count')
    axes[0, 0].set_xlabel('')
    axes[0, 0].set_ylabel('Contributors')

    sns.boxplot(ax=axes[0, 1], x='group_2b', y='stars', data=df, palette="pastel", showfliers=False)
    axes[0, 1].set_title('Repository Stars')
    axes[0, 1].set_xlabel('')
    axes[0, 1].set_ylabel('Stars')

    sns.boxplot(ax=axes[1, 0], x='group_2b', y='size_kb', data=df, palette="pastel", showfliers=False)
    axes[1, 0].set_title('Repository Size (KB)')
    axes[1, 0].set_xlabel('Group')
    axes[1, 0].set_ylabel('Size (KB)')

    sns.boxplot(ax=axes[1, 1], x='group_2b', y='project_age_days', data=df, palette="pastel", showfliers=False)
    axes[1, 1].set_title('Project Age (Days)')
    axes[1, 1].set_xlabel('Group')
    axes[1, 1].set_ylabel('Age (Days)')

    plt.tight_layout()
    plt.savefig(os.path.join(SAVE_DIR, '08_rq2_confounding_variables_boxplots.png'))
    plt.close()

    # --- NEW Plot 9: Test 2f - Bug-Fix Ratio by Config Type ---
    print("Generating Plot 9: RQ2 (Test 2f) - Bug-Fix Ratio by Config Type...")
    # Create the combined DataFrame for plotting
    no_eslint_group['config_type_group'] = 'No ESLint'
    valid_eslint_group['config_type_group'] = valid_eslint_group['config_type']

    plot_df_2f = pd.concat([no_eslint_group, valid_eslint_group[valid_eslint_group['config_type'] != 'Unknown']])

    plt.figure(figsize=(10, 7))
    sns.boxplot(x='config_type_group', y='bug_fix_ratio', data=plot_df_2f,
                palette="pastel",
                showfliers=False)

    plt.title('RQ2 (Test 2f): Bug-Fix Ratio by Config Type', fontsize=16)
    plt.xlabel('Configuration Type')
    plt.ylabel('Bug-Fix Ratio')
    plt.ylim(0, 0.5)
    plt.savefig(os.path.join(SAVE_DIR, '09_rq2_bug_ratio_by_config_type_boxplot.png'))
    plt.close()

    # --- NEW Plot 10: Test 3d - Strictness by Config Type ---
    print("Generating Plot 10: RQ3 (Test 3d) - Strictness by Config Type...")
    plot_df_3d = valid_eslint_group[valid_eslint_group['config_type'] != 'Unknown'].copy()
    plot_df_3d['relative_strictness_pct'] = plot_df_3d['relative_strictness'] * 100

    plt.figure(figsize=(8, 7))
    sns.boxplot(x='config_type', y='relative_strictness_pct', data=plot_df_3d,
                palette="pastel")

    plt.title('RQ3 (Test 3d): Relative Strictness by Config Type', fontsize=16)
    plt.xlabel('Configuration Type')
    plt.ylabel('Relative Strictness (%)')
    plt.savefig(os.path.join(SAVE_DIR, '10_rq3_strictness_by_config_type_boxplot.png'))
    plt.close()

    # --- NEW Plot 11: Test 3e - Regression Coefficient Plot ---
    print("Generating Plot 11: RQ3 (Test 3e) - Regression Coefficient Plot...")

    # --- Rerun the final regression model (Test 3e) to get data ---
    eslint_data = valid_eslint_group.copy()
    Y = eslint_data['bug_fix_ratio']
    X_base = df.loc[eslint_data.index][['log_age', 'log_size', 'log_contributors', 'log_stars']]
    X_dummies = pd.get_dummies(eslint_data['strictness_category'], prefix='strictness', drop_first=True, dtype=int)
    X = pd.concat([X_base, X_dummies], axis=1)
    X = sm.add_constant(X, has_constant='add')
    final_data = pd.concat([Y, X], axis=1).dropna()
    Y_final = final_data['bug_fix_ratio']
    X_final = final_data.drop('bug_fix_ratio', axis=1)
    Y_final = pd.to_numeric(Y_final, errors='coerce')
    X_final = X_final.apply(pd.to_numeric, errors='coerce')
    final_data_numeric = pd.concat([Y_final, X_final], axis=1).dropna()
    Y_final = final_data_numeric['bug_fix_ratio']
    X_final = final_data_numeric.drop('bug_fix_ratio', axis=1)

    model_log = sm.OLS(Y_final, X_final).fit()

    # --- Create the Coefficient Plot ---
    conf = model_log.conf_int()  # Get 95% confidence intervals
    params = model_log.params  # Get coefficients

    # Combine into a DataFrame
    coef_df = pd.DataFrame({
        'param': params.index,
        'coef': params.values,
        'conf_low': conf[0],
        'conf_high': conf[1]
    })

    # Drop the 'const' (intercept) for a cleaner plot
    coef_df = coef_df[coef_df['param'] != 'const']

    plt.figure(figsize=(10, 6))

    # Plot coefficients as points
    plt.scatter(x=coef_df['coef'], y=coef_df['param'], s=80, color='b')

    # Plot confidence intervals as lines
    plt.hlines(y=coef_df['param'], xmin=coef_df['conf_low'], xmax=coef_df['conf_high'],
               color='b', alpha=0.5, lw=3)

    # Add a vertical line at 0 for reference
    plt.axvline(x=0, color='red', linestyle='--', lw=1)

    plt.title('RQ3 (Test 3e): Regression Model Coefficients (95% CI)', fontsize=16)
    plt.xlabel('Coefficient Value')
    plt.ylabel('Model Variable')
    plt.grid(axis='x')

    # --- FIX ---
    # Add tight_layout() to prevent labels from being cut off
    plt.tight_layout()

    plt.savefig(os.path.join(SAVE_DIR, '11_rq3_regression_coefficient_plot.png'))
    plt.close()

    print("\n--- Visualization Complete ---")
    print(f"All {len(os.listdir(SAVE_DIR))} plots have been saved to the '{SAVE_DIR}' directory.")


if __name__ == "__main__":
    create_visualizations()