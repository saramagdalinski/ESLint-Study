import pandas as pd
import requests
import time
import re
from tqdm import tqdm
import os
import random

# --- CONFIGURATION ---

# Read token from environment variable
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN environment variable not set.")
    print("Please set it before running the script:")
    print("export GITHUB_TOKEN='your_token_here'")
    exit(1)

# --- Your Cluster Sampling Strategy ---
REPOS_TO_SAMPLE = 25
COMMITS_PER_REPO = 10
# --------------------------------------

# Set file paths (relative to a 'scripts' directory, e.g.)
INPUT_CSV_FILE = os.path.join('..', 'data', 'processed', 'repos_with_bug_fix_ratios.csv')
OUTPUT_CSV_FILE = os.path.join('..', 'data', 'processed', 'manual_checkout_list.csv')

# Keywords to search for in commit messages (from your script)
BUG_FIX_KEYWORDS = [r'\bbug\b', r'\bfix\b']
keyword_regex = re.compile('|'.join(BUG_FIX_KEYWORDS), re.IGNORECASE)

# --- SCRIPT ---

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}


def get_bug_commits_for_repo(repo_full_name, target_count):
    """
    Fetches commits for a repo's default branch until it finds
    `target_count` bug-fix commits.
    """
    owner, repo = repo_full_name.split('/')
    api_url = f"https://api.github.com/repos/{owner}/{repo}/commits"

    bug_commit_shas = []
    page = 1

    while len(bug_commit_shas) < target_count:
        try:
            params = {'per_page': 100, 'page': page}
            response = requests.get(api_url, headers=HEADERS, params=params)

            if response.status_code == 403 and 'rate limit' in response.text.lower():
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                sleep_time = max(reset_time - time.time(), 1) + 5
                print(f"Rate limit hit listing commits for {repo_full_name}. Sleeping for {sleep_time:.0f}s...")
                time.sleep(sleep_time)
                continue

            if response.status_code == 404 or response.status_code == 409:
                print(f"Repo {repo_full_name} not found or is empty. Skipping.")
                return [], 'repo_not_found_or_empty'

            response.raise_for_status()

            commits = response.json()
            if not commits:
                break  # No more commits

            for commit in commits:
                message = commit['commit']['message']

                # *** THIS IS THE NEW LINE ***
                # We only want non-merge commits (i.e., commits with only 1 parent)
                is_merge_commit = len(commit.get('parents', [])) > 1

                if keyword_regex.search(message) and not is_merge_commit:
                    bug_commit_shas.append(commit['sha'])
                    if len(bug_commit_shas) >= target_count:
                        break  # Found enough for this repo

            if 'next' not in response.links:
                break  # No more pages

            page += 1

            # Safety break to avoid infinite loops on weird repos
            if page > 100:
                print(
                    f"Warning: Searched 10,000 commits for {repo_full_name} and didn't find {target_count} bug fixes. Moving on.")
                break

        except requests.exceptions.RequestException as e:
            print(f"Error listing commits for {repo_full_name}: {e}")
            return [], f'error: {e}'
        except Exception as e:
            print(f"Unexpected error for {repo_full_name}: {e}")
            return [], f'unexpected_error: {e}'

    return bug_commit_shas, 'success'


# --- Main Execution ---

# 1. Load all repos
print("Loading list of all repos...")
try:
    df_all_repos = pd.read_csv(INPUT_CSV_FILE)
except FileNotFoundError:
    print(f"Error: Input file not found at {INPUT_CSV_FILE}")
    exit(1)

# 2. Filter for analysis_status == 'success'
if 'analysis_status' not in df_all_repos.columns:
    print(f"Error: Column 'analysis_status' not found in {INPUT_CSV_FILE}")
    print("Cannot filter for 'success'. Please check your input file.")
    exit(1)

df_successful_repos = df_all_repos[df_all_repos['analysis_status'] == 'success']
print(f"Found {len(df_successful_repos)} repos with 'success' status (out of {len(df_all_repos)} total).")

# 3. Sample repos
actual_sample_size = min(REPOS_TO_SAMPLE, len(df_successful_repos))
if actual_sample_size < REPOS_TO_SAMPLE:
    print(f"Warning: Only found {actual_sample_size} successful repos to sample from.")

print(f"Randomly sampling {actual_sample_size} repos from the 'success' group...")
df_sample = df_successful_repos.sample(n=actual_sample_size, random_state=42)  # Reproducible sample

# 4. Resumable logic
# *** IMPORTANT: Delete your old 'manual_checkout_list.csv' before running ***
if os.path.exists(OUTPUT_CSV_FILE):
    print(f"Warning: Output file {OUTPUT_CSV_FILE} already exists.")
    print("Please delete it before running this script to ensure a clean list.")
    # Simple resumable logic:
    try:
        df_existing = pd.read_csv(OUTPUT_CSV_FILE)
        processed_repos = set(df_existing['repo_full_name'])
        print(f"Found {len(processed_repos)} already processed repos in existing file. Will skip them.")
    except pd.errors.EmptyDataError:
        processed_repos = set()
        print("Existing output file is empty. Will start fresh.")
else:
    processed_repos = set()

header_needed = not os.path.exists(OUTPUT_CSV_FILE) or processed_repos == set()

# Filter sample to only those not yet processed
df_sample_to_run = df_sample[~df_sample['repo_full_name'].isin(processed_repos)]

if df_sample_to_run.empty:
    print("All sampled repos have already been processed.")
    print(f"Your analysis file is ready: {OUTPUT_CSV_FILE}")
    exit(0)

print(f"Processing {len(df_sample_to_run)} repos to find {COMMITS_PER_REPO} non-merge bug-fix commits from each...")

# 5. Run processing
for index, row in tqdm(df_sample_to_run.iterrows(), desc="Processing Repos", total=len(df_sample_to_run)):
    repo_name = row['repo_full_name']

    # --- Get bug-fix SHAs for this repo ---
    bug_shas, status = get_bug_commits_for_repo(repo_name, COMMITS_PER_REPO)

    if not bug_shas:
        print(f"No non-merge bug-fix commits found for {repo_name}. Skipping.")
        continue

    print(f"Found {len(bug_shas)} bug-fix SHAs for {repo_name}.")

    # --- Prepare data for saving ---
    clone_url = f"https://github.com/{repo_name}.git"

    new_commits_for_this_repo = []
    for sha in bug_shas:
        new_commits_for_this_repo.append({
            'repo_full_name': repo_name,
            'repo_clone_url': clone_url,
            'bug_fix_commit_sha': sha
        })

    if new_commits_for_this_repo:
        df_new = pd.DataFrame(new_commits_for_this_repo)
        df_new.to_csv(OUTPUT_CSV_FILE, mode='a', header=header_needed, index=False)
        header_needed = False

print(f"\nProcessing complete!")
print(f"List of commits for manual checkout saved to '{OUTPUT_CSV_FILE}'")