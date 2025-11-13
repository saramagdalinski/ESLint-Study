import pandas as pd
import requests
import time
import re
from tqdm import tqdm
import os

# --- CONFIGURATION ---

# Read token from environment variable
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# Set file paths
INPUT_CSV_FILE = os.path.join('..', 'data', 'processed', 'repos_with_strictness_analysis.csv')
OUTPUT_CSV_FILE = os.path.join('..', 'data', 'processed', 'repos_with_bug_fix_ratios.csv')

# Keywords to search for in commit messages
BUG_FIX_KEYWORDS = [r'\bbug\b', r'\bfix\b']
keyword_regex = re.compile('|'.join(BUG_FIX_KEYWORDS), re.IGNORECASE)

# --- SCRIPT ---

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}


def get_commit_stats(repo_full_name):
    """
    Fetches all commits for a repo's default branch and counts
    total vs. bug-fix commits.
    """
    owner, repo = repo_full_name.split('/')
    api_url = f"https://api.github.com/repos/{owner}/{repo}/commits"

    total_commits = 0
    bug_fix_commits = 0
    page = 1

    while True:
        try:
            params = {'per_page': 100, 'page': page}
            response = requests.get(api_url, headers=HEADERS, params=params)

            # Rate limit hit, sleep for a bit
            if response.status_code == 403 and 'rate limit' in response.text.lower():
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                sleep_time = max(reset_time - time.time(), 1) + 5  # Add 5s buffer
                print(f"Rate limit hit for {repo_full_name}. Sleeping for {sleep_time:.0f}s...")
                time.sleep(sleep_time)
                continue  # Retry the same page

            # Repo not found or empty, skip it
            if response.status_code == 404 or response.status_code == 409:
                print(f"Repo {repo_full_name} not found or is empty. Skipping.")
                return total_commits, bug_fix_commits, 'repo_not_found_or_empty'

            response.raise_for_status()

            commits = response.json()
            if not commits:
                break  # No more commits

            total_commits += len(commits)

            for commit in commits:
                message = commit['commit']['message']
                if keyword_regex.search(message):
                    bug_fix_commits += 1

            # Check for next page
            if 'next' not in response.links:
                break

            page += 1

        except requests.exceptions.RequestException as e:
            print(f"Error processing {repo_full_name}: {e}")
            return total_commits, bug_fix_commits, f'error: {e}'
        except Exception as e:
            print(f"An unexpected error occurred for {repo_full_name}: {e}")
            return total_commits, bug_fix_commits, f'unexpected_error: {e}'

    return total_commits, bug_fix_commits, 'success'


# --- Main Execution ---
df = pd.read_csv(INPUT_CSV_FILE)

# --- Resumable Logic ---
processed_repos = set()
results_list = []

# Define what a "processed" status looks like
VALID_STATUSES = {'success', 'repo_not_found_or_empty', 'error'}

if os.path.exists(OUTPUT_CSV_FILE):
    print(f"Found existing output file. Loading processed repos...")
    try:
        df_existing = pd.read_csv(OUTPUT_CSV_FILE)

        # A repo is only "processed" if its status is one of the valid end states.
        processed_df = df_existing[df_existing['processing_status'].isin(VALID_STATUSES)]
        processed_repos = set(processed_df['repo_full_name'])

        print(f"Found {len(processed_repos)} already processed repos. Will skip them.")
        results_list = df_existing.to_dict('records')

    except Exception as e:
        print(f"Error reading existing output file: {e}. Starting from scratch.")
        results_list = []  # Reset
        processed_repos = set()  # Reset

# If the file didn't exist or was corrupt, create it from scratch
if not results_list:
    print("No valid output file found. Starting from scratch.")
    df_existing = df.copy()
    df_existing['total_commits'] = pd.NA
    df_existing['bug_fix_commits'] = pd.NA
    df_existing['bug_fix_ratio'] = pd.NA
    df_existing['processing_status'] = pd.NA
    df_existing.to_csv(OUTPUT_CSV_FILE, index=False)
    results_list = df_existing.to_dict('records')

# Create a dictionary for quick lookup and update
results_dict = {row['repo_full_name']: row for row in results_list}

print("Running on all repos...")

# Use tqdm to loop over the original dataframe
for index, row in tqdm(df.iterrows(), desc="Processing Repositories", total=len(df)):
    repo_name = row['repo_full_name']

    # Skip if already processed
    if repo_name in processed_repos:
        continue

    # --- Run the processing ---
    total, bug_fix, status = get_commit_stats(repo_name)

    if total > 0:
        bug_fix_ratio = bug_fix / total
    else:
        bug_fix_ratio = 0.0  # Avoid division by zero

    # Update the data in our dictionary
    if repo_name in results_dict:
        results_dict[repo_name]['total_commits'] = total
        results_dict[repo_name]['bug_fix_commits'] = bug_fix
        results_dict[repo_name]['bug_fix_ratio'] = bug_fix_ratio
        results_dict[repo_name]['processing_status'] = status

    # Save progress to file incrementally
    if index % 10 == 0:  # Save every 10 repos
        pd.DataFrame.from_dict(results_dict.values()).to_csv(OUTPUT_CSV_FILE, index=False)

# --- Final Save ---
final_df = pd.DataFrame.from_dict(results_dict.values())
final_df.to_csv(OUTPUT_CSV_FILE, index=False)

print(f"\nProcessing complete!")
print(f"Results saved to '{OUTPUT_CSV_FILE}'")