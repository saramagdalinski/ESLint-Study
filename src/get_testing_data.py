import pandas as pd
import os
import subprocess
import shutil
import json
import re
from tqdm import tqdm

# --- Config ---
INPUT_FILE = os.path.join('..', 'data', 'processed', 'repos_with_bug_fix_ratios.csv') 
OUTPUT_FILE = os.path.join('..', 'data', 'processed', 'complete_dataset.csv')
TEMP_DIR = 'temp_clones'

# List of frameworks to hunt for in package.json
TEST_FRAMEWORKS = [
    'jest', 'mocha', 'vitest', 'cypress', 'playwright',
    'ava', 'jasmine', 'karma', 'puppeteer', 'selenium', 'bun:test', 'tape',
    'supertest', 'chai'
]

# Regex to catch test files (jest, specs, __tests__, etc.)
TEST_FILE_PATTERN = re.compile(r'.*(\.|/)(test|spec|__tests__)\.(ts|tsx|js|jsx)$', re.IGNORECASE)
# Regex for actual source code
CODE_FILE_PATTERN = re.compile(r'.*\.(ts|tsx|js|jsx)$', re.IGNORECASE)


def analyze_repo(repo_url):
    """
    Shallow clones the repo to check for tests, CI, strict mode, and test frameworks.
    """
    metrics = {
        'test_code_ratio': 0.0,
        'test_file_density': 0.0,
        'ts_strict_mode': False,
        'has_ci': False,
        'has_tests': False,
        'test_framework': 'None'  # Default if nothing found
    }

    # Clear out any junk from a previous run
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

    try:
        # Shallow clone only the latest commit (way faster)
        subprocess.run(
            ['git', 'clone', '--depth', '1', repo_url, TEMP_DIR],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        # If the repo is gone or private, just return empty metrics
        return metrics

    total_code_lines = 0
    test_code_lines = 0
    total_files = 0
    test_files = 0
    found_frameworks = set()

    # Walk the file tree
    for root, dirs, files in os.walk(TEMP_DIR):
        # Ignore heavy dependencies and git internals
        if 'node_modules' in dirs: dirs.remove('node_modules')
        if '.git' in dirs: dirs.remove('.git')

        for file in files:
            file_path = os.path.join(root, file)

            # 1. Look for CI configs (GitHub Actions, Travis, etc.)
            if not metrics['has_ci']:
                if file in ['jenkinsfile', '.travis.yml', 'circle.yml'] or \
                        (root.endswith('.github/workflows') and file.endswith(('.yml', '.yaml'))):
                    metrics['has_ci'] = True

            # 2. Check tsconfig for strict mode
            if file == 'tsconfig.json' and not metrics['ts_strict_mode']:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        # Strip comments so json.loads doesn't choke
                        content = re.sub(r'//.*', '', f.read())
                        data = json.loads(content)
                        if data.get('compilerOptions', {}).get('strict') is True:
                            metrics['ts_strict_mode'] = True
                except:
                    pass  # Malformed json, skip it

            # 3. Check package.json for Testing Frameworks
            if file == 'package.json':
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        pkg = json.load(f)
                        # Combine dev and regular dependencies
                        all_deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}

                        # Check if any of our known frameworks are in the deps
                        for fw in TEST_FRAMEWORKS:
                            if any(d for d in all_deps if fw in d):
                                found_frameworks.add(fw)
                except:
                    pass

            # 4. Count lines of code for Ratio
            if CODE_FILE_PATTERN.match(file):
                total_files += 1
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = sum(1 for _ in f)
                        total_code_lines += lines

                        if TEST_FILE_PATTERN.match(file_path):
                            test_files += 1
                            test_code_lines += lines
                            metrics['has_tests'] = True
                except:
                    pass

    # Calculate final ratios
    if total_code_lines > 0:
        metrics['test_code_ratio'] = round(test_code_lines / total_code_lines, 4)

    if total_files > 0:
        metrics['test_file_density'] = round(test_files / total_files, 4)

    # Format frameworks as a string for the CSV
    if found_frameworks:
        metrics['test_framework'] = ', '.join(sorted(list(found_frameworks)))
        metrics['has_tests'] = True  # If they installed a framework, they probably have tests

    # Clean up disk space
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    return metrics


# --- Main ---

print("Loading dataset...")
df = pd.read_csv(INPUT_FILE)

# Init columns if they don't exist yet
for col in ['test_code_ratio', 'test_file_density', 'ts_strict_mode', 'has_ci', 'has_tests', 'test_framework']:
    if col not in df.columns:
        df[col] = None

print(f"Processing {len(df)} repositories...")

for index, row in tqdm(df.iterrows(), total=df.shape[0]):
    url = row['html_url']

    # Skip missing URLs
    if pd.isna(url):
        continue

    # Skip rows we already processed (useful if script crashes/restarts)
    if pd.notna(row['test_code_ratio']) and row['test_code_ratio'] != "":
        continue

    results = analyze_repo(url)

    # Update the dataframe
    df.at[index, 'test_code_ratio'] = results['test_code_ratio']
    df.at[index, 'test_file_density'] = results['test_file_density']
    df.at[index, 'ts_strict_mode'] = results['ts_strict_mode']
    df.at[index, 'has_ci'] = results['has_ci']
    df.at[index, 'has_tests'] = results['has_tests']
    df.at[index, 'test_framework'] = results['test_framework']

    # Incremental save every 50 rows just in case
    if index % 50 == 0:
        df.to_csv(OUTPUT_FILE, index=False)

# Final save
df.to_csv(OUTPUT_FILE, index=False)
print(f"Done. Saved to {OUTPUT_FILE}")

# Get the stats for the paper
if 'bug_fix_ratio' in df.columns:
    print("\n--- Stats ---")
    # Ensure columns are numeric for correlation
    df['test_code_ratio'] = pd.to_numeric(df['test_code_ratio'], errors='coerce')
    df['ts_strict_mode'] = df['ts_strict_mode'].astype(bool)  # Ensure bool is treated as 0/1

    print("Correlation (Bug Fix Ratio vs Test Code Ratio):")
    print(df['bug_fix_ratio'].corr(df['test_code_ratio']))

    print("\nCorrelation (Bug Fix Ratio vs Strict Mode):")
    print(df['bug_fix_ratio'].corr(df['ts_strict_mode']))