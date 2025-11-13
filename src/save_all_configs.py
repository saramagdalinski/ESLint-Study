import pandas as pd
import subprocess
import json
import os
import shutil
import glob
import time

# --- Configuration ---

# 1. Path to Node.js helper script
NODE_HELPER_SCRIPT = '../eslint-helper/get_config.js'

# 2. Input CSV file name
INPUT_CSV = 'typescript_repos_metadata_filtered.csv'

# 3. Path for cloning repos
TEMP_REPO_PATH = os.path.abspath('temp_repo_for_saving_configs')

# 4. Directory to save the final config files
CONFIG_SAVE_DIR = '../eslint_configs'


# --- Helper Functions ---

def save_config_file(repo_name, json_string):
    """
    Saves the provided JSON string to a file.
    """
    try:
        if not os.path.exists(CONFIG_SAVE_DIR):
            os.makedirs(CONFIG_SAVE_DIR)

        # Sanitize repo_name: "microsoft/vscode" -> "microsoft_vscode"
        safe_name = repo_name.replace('/', '_')
        filename = f"{safe_name}_ESLintConfiguration.json"
        filepath = os.path.join(CONFIG_SAVE_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            # "Pretty-print" the JSON string
            pretty_json = json.dumps(json.loads(json_string), indent=2)
            f.write(pretty_json)
        print(f"  -> Saved config to {filepath}")
        return True

    except IOError as e:
        print(f"  -> Error saving config file: {e}")
        return False
    except json.JSONDecodeError:
        print(f"  -> Error: Tried to save invalid JSON.")
        return False


def get_eslint_config_string(repo_root_path, config_file_relative_path):
    """
    Finds a .ts file near the config and runs the node helper
    script to get the final computed ESLint configuration.

    Returns the RAW JSON STRING on success.
    """
    config_file_full_path = os.path.join(repo_root_path, config_file_relative_path)
    config_dir = os.path.dirname(config_file_full_path)

    ts_files = glob.glob(os.path.join(config_dir, '**', '*.ts'), recursive=True)
    if not ts_files:
        ts_files = glob.glob(os.path.join(repo_root_path, '**', '*.ts'), recursive=True)

    if not ts_files:
        print(f"  -> No .ts files found in {repo_root_path}. Skipping.")
        return None

    probe_file_path = ts_files[0]

    try:
        process_args = [
            'node',
            NODE_HELPER_SCRIPT,
            probe_file_path,
            config_file_full_path,
            repo_root_path
        ]

        process = subprocess.run(
            process_args,
            capture_output=True, text=True, check=True, timeout=120
        )

        # Return the raw text output from the node script
        return process.stdout

    except subprocess.CalledProcessError as e:
        print(f"  -> Error running Node.js script: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"  -> An unexpected error occurred: {e}")
        return None


def download_and_save_config(repo_url, config_file_relative_path, repo_name):
    """
    Clones, installs dependencies, saves config, and cleans up.
    Returns True on success, False on failure.
    """
    try:
        # 1. Clone
        clone_url = repo_url if repo_url.endswith('.git') else f"{repo_url}.git"
        subprocess.run(
            ['git', 'clone', '--depth', '1', clone_url, TEMP_REPO_PATH],
            check=True, capture_output=True, timeout=300
        )

        # 2. Install dependencies
        print("  -> Running 'npm install'...")
        try:
            subprocess.run(
                ['npm', 'install'],
                cwd=TEMP_REPO_PATH,
                check=True,
                capture_output=True,
                timeout=300
            )
            print("  -> 'npm install' complete.")
        except subprocess.CalledProcessError as e:
            print(f"  -> 'npm install' failed: {e.stderr.decode('utf-8').strip()}")
            return False
        except subprocess.TimeoutExpired:
            print(f"  -> 'npm install' timed out.")
            return False

        # 3. Get the config string
        raw_json_string = get_eslint_config_string(TEMP_REPO_PATH, config_file_relative_path)

        if raw_json_string is None:
            return False  # get_eslint_config failed

        # 4. Save the raw config file
        return save_config_file(repo_name, raw_json_string)

    except subprocess.CalledProcessError as e:
        print(f"  -> Failed to clone {repo_url}: {e.stderr.decode('utf-8').strip()}")
        return False
    except subprocess.TimeoutExpired:
        print(f"  -> Timeout cloning {repo_url}.")
        return False
    finally:
        # 5. Clean up
        if os.path.exists(TEMP_REPO_PATH):
            shutil.rmtree(TEMP_REPO_PATH)


# --- Main Execution ---

def main():
    print(f"--- Starting Config-Saving Script ---")
    print(f"Loading repositories from {INPUT_CSV}...")
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"Error: Could not find {INPUT_CSV}.")
        return

    # --- Required Column Names ---
    URL_COLUMN = 'html_url'
    LINTER_COLUMN = 'has_eslint'
    CONFIG_PATH_COLUMN = 'eslint_config_path'
    REPO_NAME_COLUMN = 'repo_full_name'
    # ----------------------------

    required_cols = [URL_COLUMN, LINTER_COLUMN, CONFIG_PATH_COLUMN, REPO_NAME_COLUMN]
    if not all(col in df.columns for col in required_cols):
        print(f"Error: CSV must contain all required columns: {required_cols}")
        print(f"Found columns: {list(df.columns)}")
        return

    # --- ADDED ---
    # New columns to track saving progress in a new CSV
    df['config_save_status'] = 'not_run'
    PROGRESS_CSV = 'config_save_progress.csv'
    # -------------

    eslint_df_indices = df[df[LINTER_COLUMN] == True].index
    print(f"Found {len(eslint_df_indices)} repositories with ESLint to check.")

    for i, index in enumerate(eslint_df_indices):
        repo_name = df.at[index, REPO_NAME_COLUMN]
        repo_url = df.at[index, URL_COLUMN]
        config_path = df.at[index, CONFIG_PATH_COLUMN]

        print(f"\nProcessing ({i + 1}/{len(eslint_df_indices)}): {repo_name}")

        success = download_and_save_config(repo_url, config_path, repo_name)

        if success:
            df.at[index, 'config_save_status'] = 'success'
        else:
            print(f"  -> Failed to save config for {repo_name}.")
            df.at[index, 'config_save_status'] = 'failed'

        # Save progress every 10 repos to a new CSV
        if (i + 1) % 10 == 0:
            print(f"\n--- Saving progress to {PROGRESS_CSV} ---")
            df.to_csv(PROGRESS_CSV, index=False)

    print(f"\nConfig saving complete. Saving final progress to {PROGRESS_CSV}.")
    df.to_csv(PROGRESS_CSV, index=False)
    print(f"All saved configs are in the '{CONFIG_SAVE_DIR}' directory.")
    print("Done.")


if __name__ == "__main__":
    # Clean up any old temp repo before starting
    if os.path.exists(TEMP_REPO_PATH):
        print(f"Cleaning up old '{TEMP_REPO_PATH}' directory...")
        shutil.rmtree(TEMP_REPO_PATH)
    main()