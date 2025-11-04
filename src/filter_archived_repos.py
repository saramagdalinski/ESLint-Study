import requests
import csv
import os
import time

# --- CONFIGURATION ---
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# The "dirty" file that has archived repos in it
INPUT_CSV = os.path.join('..', 'data', 'raw', 'typescript_repos_metadata.csv')

# The new, clean output file
OUTPUT_CSV = os.path.join('..', 'data', 'raw', 'typescript_repos_metadata_removed_archived.csv')


# --- SCRIPT LOGIC ---

def get_repo_archived_status(owner, repo, headers):
    """
    Makes a single API call to check the 'archived' status of a repo.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Check rate limit
        if 'X-RateLimit-Remaining' in response.headers and int(response.headers['X-RateLimit-Remaining']) < 20:
            print("Rate limit low, sleeping for 60 seconds...")
            time.sleep(60)

        data = response.json()
        return data.get('archived', False)  # Returns True or False

    except requests.exceptions.HTTPError as e:
        print(f"  > Warning: Could not fetch {owner}/{repo}. Skipping. Error: {e}")
        return "ERROR_SKIP"  # Skip this repo
    except requests.exceptions.RequestException as e:
        print(f"  > Network Error for {owner}/{repo}. Skipping. Error: {e}")
        return "ERROR_SKIP"


def filter_archived_repos():
    """
    Reads the input CSV, checks each repo's 'archived' status,
    and writes the non-archived repos to a new file.
    """
    if not GITHUB_TOKEN:
        raise ValueError("GitHub token not found. Set the GITHUB_TOKEN environment variable.")

    core_headers = {'Authorization': f'Bearer {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}

    input_rows = []
    try:
        with open(INPUT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            input_rows = list(reader)
            fieldnames = reader.fieldnames
    except FileNotFoundError:
        print(f"ERROR: Input file not found. Make sure this file exists: {INPUT_CSV}")
        return
    except Exception as e:
        print(f"ERROR: Could not read {INPUT_CSV}. Error: {e}")
        return

    if not input_rows or not fieldnames:
        print(f"ERROR: Input file {INPUT_CSV} is empty.")
        return

    print(f"Loaded {len(input_rows)} repositories from {INPUT_CSV}.")
    print("Beginning filtering for archived repositories...")

    archived_count = 0
    final_count = 0

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, row in enumerate(input_rows):
            full_name = row['repo_full_name']
            owner, repo = full_name.split('/')

            print(f"({i + 1}/{len(input_rows)}) Checking: {full_name}")

            archived_status = get_repo_archived_status(owner, repo, core_headers)

            if archived_status == "ERROR_SKIP":
                continue  # Skip repos that couldn't be checked (e.g., 404)

            if archived_status == True:
                print(f"  > FILTERED (Archived): {full_name}")
                archived_count += 1
            else:
                # This repo is NOT archived, so we keep it.
                writer.writerow(row)
                final_count += 1

    print("\n--- Filtering Complete ---")
    print(f"Total repos processed: {len(input_rows)}")
    print(f"Archived repos filtered out: {archived_count}")
    print(f"New dataset size: {final_count}")
    print(f"Clean data saved to: {OUTPUT_CSV}")


# --- EXECUTE THE SCRIPT ---
if __name__ == "__main__":
    filter_archived_repos()