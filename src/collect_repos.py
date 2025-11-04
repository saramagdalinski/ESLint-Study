import requests
import csv
import os
import time
import re
import subprocess
import shutil

# --- CONFIGURATION ---
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

LINTER_FILENAMES = [
    # New "flat config" files
    'eslint.config.js',
    'eslint.config.mjs',
    'eslint.config.cjs',
    'eslint.config.ts',
    'eslint.config.mts',
    'eslint.config.cts',
    # Deprecated ".eslintrc" files
    '.eslintrc.js',
    '.eslintrc.cjs',
    '.eslintrc.json',
    '.eslintrc.yaml',
    '.eslintrc.yml',
    '.eslintrc'
]

UNPARSABLE_FILENAMES = [
    'eslint.config.ts',
    'eslint.config.mts',
    'eslint.config.cts'
]


# --- API HELPER FUNCTIONS ---

def get_contributors_count(owner, repo, headers):
    """
    Efficiently gets the total contributor count by parsing the 'Link' header.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
    params = {'per_page': 1, 'anon': 'true'}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()

        link_header = response.headers.get('Link')
        if not link_header:
            data = response.json()
            return len(data) if isinstance(data, list) else 0
        match = re.search(r'page=(\d+)>; rel="last"', link_header)
        if match: return int(match.group(1))
        data = response.json()
        return len(data) if isinstance(data, list) else 1
    except requests.exceptions.RequestException as e:
        print(f"  > Network error getting contributors for {owner}/{repo}: {e}")
        return None


def check_repo_for_linter(owner, repo, core_headers):
    """
    Robust 2-step check.
    1. Checks root directory (fast) using Core API.
    2. If not found, clones the repo locally (slow but reliable) and searches.

    Returns: (file_path, is_parsable)
    Returns (None, False) if no file is found.
    Returns ("ERROR_SKIP", False) if the repo can't be processed.
    """

    # --- Step 1: Check root directory (Fast) ---
    root_url = f"https://api.github.com/repos/{owner}/{repo}/contents/"
    try:
        response = requests.get(root_url, headers=core_headers, timeout=15)
        if response.status_code == 200:
            repo_files = response.json()
            if isinstance(repo_files, list):
                filenames = {file_info['name'] for file_info in repo_files if file_info['type'] == 'file'}
                for linter_file in LINTER_FILENAMES:
                    if linter_file in filenames:
                        print(f"  > Found linter in root: {linter_file}")
                        is_parsable = linter_file not in UNPARSABLE_FILENAMES
                        return linter_file, is_parsable
        elif response.status_code in [404, 403]:
            print(f"  > Warning: Repo {owner}/{repo} is empty or restricted. Will attempt to clone.")
    except requests.exceptions.RequestException as e:
        print(f"  > Network error checking root. Will attempt to clone. Error: {e}")

    # --- Step 2: Not in root. Clone and search locally (Reliable) ---
    print("  > Not in root. Cloning repository locally to search...")

    repo_url = f"https://github.com/{owner}/{repo}.git"
    temp_clone_dir = os.path.join("temp_clones", repo)

    os.makedirs("temp_clones", exist_ok=True)

    try:
        subprocess.run(
            ['git', 'clone', '--depth', '1', repo_url, temp_clone_dir],
            check=True, capture_output=True, text=True
        )

        for root, dirs, files in os.walk(temp_clone_dir):
            for filename in LINTER_FILENAMES:
                if filename in files:
                    full_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(full_path, temp_clone_dir)

                    print(f"  > Found linter in sub-directory: {relative_path}")

                    is_parsable = filename not in UNPARSABLE_FILENAMES
                    return relative_path, is_parsable

        print("  > No linter found after cloning.")
        return None, False

    except subprocess.CalledProcessError as e:
        print(f"  > ERROR: Failed to clone {repo_url}. Skipping. Error: {e.stderr}")
        return "ERROR_SKIP", False
    except Exception as e:
        print(f"  > An unexpected error occurred during local search: {e}")
        return "ERROR_SKIP", False
    finally:
        if os.path.exists(temp_clone_dir):
            shutil.rmtree(temp_clone_dir)


# --- MAIN DATA COLLECTION LOGIC ---

def collect_repos(output_csv, max_repos=1000):
    if not GITHUB_TOKEN:
        raise ValueError("GitHub token not found.")

    core_headers = {'Authorization': f'Bearer {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}

    print(f"Starting repository collection. Target: {max_repos} repos.")
    repo_search_url = "https://api.github.com/search/repositories"

    query = 'language:typescript -is:fork -is:archived stars:>50 size:1000..100000 pushed:>2024-11-03'
    params = {'q': query, 'sort': 'help-wanted-issues', 'order': 'desc', 'per_page': 100, 'page': 1}

    repos_collected = 0
    linter_count = 0
    no_linter_count = 0

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'repo_full_name', 'has_eslint', 'eslint_config_path', 'is_parsable',
            'contributors_count', 'stars', 'size_kb', 'forks', 'open_issues',
            'created_at', 'pushed_at', 'html_url'
        ])

        while repos_collected < max_repos:
            try:
                print(f"Requesting page {params['page']} of repo search results...")
                response = requests.get(repo_search_url, headers=core_headers, params=params)
                response.raise_for_status()

                data = response.json()
                items = data.get('items', [])
                if not items:
                    print("No more search results found.")
                    break

                for repo in items:
                    if repos_collected >= max_repos:
                        break

                    full_name = repo['full_name']
                    owner, repo_name = full_name.split('/')

                    print(f"({repos_collected + 1}/{max_repos}) Checking: {full_name}")

                    config_path, is_parsable = check_repo_for_linter(owner, repo_name, core_headers)

                    if config_path == "ERROR_SKIP":
                        continue

                    has_linter = config_path is not None

                    contributors_count = get_contributors_count(owner, repo_name, core_headers)
                    if contributors_count is None:
                        continue

                    writer.writerow([
                        full_name,
                        has_linter,
                        config_path if has_linter else 'N/A',
                        is_parsable if has_linter else 'N/A',
                        contributors_count,
                        repo['stargazers_count'], repo['size'], repo['forks_count'],
                        repo['open_issues_count'], repo['created_at'], repo['pushed_at'], repo['html_url']
                    ])

                    repos_collected += 1
                    if has_linter:
                        linter_count += 1
                    else:
                        no_linter_count += 1

                print(
                    f"Page {params['page']} complete. Status: {linter_count} w/ ESLint, {no_linter_count} w/o ESLint.")
                params['page'] += 1
                time.sleep(2)

            except requests.exceptions.RequestException as e:
                print(f"Major Network Error: {e}. Sleeping and retrying...")
                time.sleep(60)

    print("\n--- Collection Complete ---")
    print(f"Total repos written to {output_csv}: {repos_collected}")
    print(f"With ESLint: {linter_count}")
    print(f"Without Linter: {no_linter_count}")


# --- EXECUTE THE SCRIPT ---
if __name__ == "__main__":
    output_path = os.path.join('..', 'data', 'raw', 'typescript_repos_metadata.csv')
    collect_repos(output_csv=output_path, max_repos=1000)