import pandas as pd
import requests
import time
import os
import base64
import json
import re
from tqdm import tqdm

# --- CONFIGURATION ---
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

INPUT_FILES = [
    os.path.join('..', 'data', 'processed', 'Commit-Analysis-Repos-No-ESLint.csv'),
    os.path.join('..', 'data', 'processed', 'Commit-Analysis-Repos-With-ESLint.csv')
]
OUTPUT_FILE = os.path.join('..', 'data', 'processed', 'deep-dive-test-analysis.csv')

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

# Standard testing libraries to detect
TEST_FRAMEWORKS = [
    'jest', 'mocha', 'vitest', 'cypress', 'playwright',
    'ava', 'jasmine', 'karma', 'puppeteer', 'selenium', 'bun:test', 'tape',
    'supertest', 'chai'
]


def get_file_content(repo_name, file_path, commit_sha):
    """Helper to fetch and decode a single file at a specific commit."""
    url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}"
    try:
        res = requests.get(url, headers=HEADERS, params={'ref': commit_sha})
        if res.status_code == 200:
            return base64.b64decode(res.json()['content']).decode('utf-8')
    except:
        pass
    return None


def analyze_commit_maturity(repo_url, commit_sha):
    """
    Analyzes the repository state at the exact moment of the bug fix commit.
    Collects metrics on Testing Investment and Static Analysis Configuration.
    """
    repo_name = repo_url.replace("https://github.com/", "").replace(".git", "").strip()

    metrics = {
        'repo': repo_name,
        'commit': commit_sha,

        # Testing Metrics
        'test_framework': 'None',
        'has_tests': False,
        'test_file_density': 0.0,  # Ratio of test files to all source files
        'test_code_ratio': 0.0,  # Ratio of test code volume (bytes) to total code volume

        # Static Analysis Metrics
        'has_ci': False,  # GitHub Actions presence
        'ts_strict_mode': False,  # Is "strict": true in tsconfig?
    }

    try:
        # 1. Framework Detection (package.json)
        pkg_content = get_file_content(repo_name, "package.json", commit_sha)
        if pkg_content:
            try:
                pkg = json.loads(pkg_content)
                all_deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}

                found = [fw for fw in TEST_FRAMEWORKS if any(d for d in all_deps if fw in d)]
                if found:
                    metrics['has_tests'] = True
                    metrics['test_framework'] = ', '.join(found)
            except json.JSONDecodeError:
                pass

        # 2. TypeScript Strictness (tsconfig.json)
        tsconfig_content = get_file_content(repo_name, "tsconfig.json", commit_sha)
        if tsconfig_content:
            # Simple regex check because tsconfig often allows comments (invalid JSON)
            if re.search(r'"strict"\s*:\s*true', tsconfig_content):
                metrics['ts_strict_mode'] = True

        # 3. Structural Analysis (File Tree)
        # We use file size (bytes) as a proxy for Lines of Code (LOC) to avoid rate limits.
        tree_url = f"https://api.github.com/repos/{repo_name}/git/trees/{commit_sha}?recursive=1"
        tree_res = requests.get(tree_url, headers=HEADERS)

        if tree_res.status_code == 200:
            tree = tree_res.json().get('tree', [])

            loc_production = 0
            loc_test = 0
            count_production = 0
            count_test = 0

            for item in tree:
                path = item.get('path', '').lower()
                size = item.get('size', 0)

                # Check for CI Config presence
                if path.startswith('.github/workflows/') and path.endswith(('.yml', '.yaml')):
                    metrics['has_ci'] = True

                if item['type'] != 'blob': continue

                # Only analyze relevant source extensions
                if not path.endswith(('.ts', '.tsx', '.js', '.jsx', '.vue', '.svelte')):
                    continue

                # Heuristic to identify Test Files
                is_test = False
                if any(x in path.split('/') for x in ['test', 'tests', '__tests__', 'spec', 'specs']):
                    is_test = True
                elif any(x in os.path.basename(path) for x in ['.test.', '.spec.', '_test.', '_spec.']):
                    is_test = True

                if is_test:
                    loc_test += size
                    count_test += 1
                else:
                    loc_production += size
                    count_production += 1

            # Calculate Ratios
            total_bytes = loc_test + loc_production
            total_files = count_test + count_production

            if total_bytes > 0:
                metrics['test_code_ratio'] = round(loc_test / total_bytes, 4)

            if total_files > 0:
                metrics['test_file_density'] = round(count_test / total_files, 4)

    except Exception as e:
        print(f"Error processing {repo_name}: {e}")

    return metrics


# --- MAIN EXECUTION ---

dfs = []
for f in INPUT_FILES:
    if os.path.exists(f):
        t = pd.read_csv(f)
        # Ensure column name consistency
        if 'Commit SHA' in t.columns: t = t.rename(columns={'Commit SHA': 'Commit'})
        dfs.append(t)

if not dfs:
    print("No input files found.")
    exit(1)

df = pd.concat(dfs, ignore_index=True)
# Filter for unique Repo/Commit pairs to avoid duplicate API calls
df_unique = df[['Repo', 'Commit']].drop_duplicates()

print(f"Analyzing {len(df_unique)} unique commits for maturity metrics...")

results = []
for index, row in tqdm(df_unique.iterrows(), total=len(df_unique)):
    m = analyze_commit_maturity(row['Repo'], row['Commit'])

    # Merge with manual qualitative data (Verdicts)
    # We look up the original row to get the 'Preventable' status
    original_row = df[(df['Repo'] == row['Repo']) & (df['Commit'] == row['Commit'])].iloc[0]

    combined = {
        'Repo': row['Repo'],
        'Commit': row['Commit'],
        'Preventable': original_row.get('Preventable? (Y/N)', 'N'),
        'Category': original_row.get('Notes', '').split('.')[0] if pd.notna(original_row.get('Notes')) else 'Unknown',
        **m
    }
    results.append(combined)

    time.sleep(0.5)  # Rate limit safety

# Save Results
final_df = pd.DataFrame(results)
final_df.to_csv(OUTPUT_FILE, index=False)

print(f"\nAnalysis Complete. Saved to {OUTPUT_FILE}")
print("\n--- Preview of Test Maturity ---")
print(final_df[['repo', 'test_code_ratio', 'ts_strict_mode', 'has_ci']].head())