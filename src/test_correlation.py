import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import scipy.stats as stats

# 1. Load Data
df = pd.read_csv(os.path.join('..', 'data', 'processed', 'test_metrics_all.csv'))

# 2. clean data (ensure numeric)
df['bug_fix_ratio'] = pd.to_numeric(df['bug_fix_ratio'], errors='coerce')
df['test_code_ratio'] = pd.to_numeric(df['test_code_ratio'], errors='coerce')

# 3. Calculate Correlations
# Pearson correlation: -1 (perfect negative) to +1 (perfect positive)
corr_test = df['bug_fix_ratio'].corr(df['test_code_ratio'])
corr_strict = df['bug_fix_ratio'].corr(df['ts_strict_mode'])

print(f"--- FINAL RESULTS ---")
print(f"n = {len(df)} Repositories")
print(f"Correlation (Test Code Ratio vs Bug Fixes): {corr_test:.4f}")
print(f"Correlation (Strict Mode vs Bug Fixes):     {corr_strict:.4f}")

# 4. Generate Plot for Paper
plt.figure(figsize=(10, 6))
sns.regplot(x='test_code_ratio', y='bug_fix_ratio', data=df,
            scatter_kws={'alpha':0.3}, line_kws={'color':'red'})

plt.title(f"Test Density vs. Bug Fix Ratio (r={corr_test:.2f})")
plt.xlabel("Test Code Ratio (Test LOC / Total LOC)")
plt.ylabel("Bug Fix Ratio (Fix Commits / Total Commits)")
plt.tight_layout()
plt.savefig('correlation_graph.png')
print("\nGraph saved to correlation_graph.png")