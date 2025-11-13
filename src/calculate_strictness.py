import pandas as pd
import subprocess
import json
import os
import shutil
import glob
import time


# Path to Node.js helper script
NODE_HELPER_SCRIPT = '../eslint-helper/get_config.js'  # Make sure this is correct

# Input and output file names
INPUT_CSV = 'typescript_repos_metadata_filtered.csv'
OUTPUT_CSV = 'repos_with_strictness_analysis.csv'

#Path for cloning repos

# Use an absolute path for the temp repo
TEMP_REPO_PATH = os.path.abspath('temp_repo_for_analysis')


def get_eslint_config(repo_root_path, config_file_relative_path):
    """
    Finds a .ts file near the config and runs the node helper
    script to get the final computed ESLint configuration.

    Passes 3 paths to the node script:
    1. probe_file_path: A .ts file to analyze.
    2. config_file_path: The path to the eslint config file.
    3. repo_root_path: The root of the cloned repo (for finding node_modules).
    """

    # We now use the known config path to find a relevant .ts file
    config_file_full_path = os.path.join(repo_root_path, config_file_relative_path)
    config_dir = os.path.dirname(config_file_full_path)

    # Find a .ts file in or below the config file's directory
    ts_files = glob.glob(os.path.join(config_dir, '**', '*.ts'), recursive=True)

    if not ts_files:
        # find any .ts file in the repo as a fallback
        ts_files = glob.glob(os.path.join(repo_root_path, '**', '*.ts'), recursive=True)

    if not ts_files:
        print(f"  -> No .ts files found in {repo_root_path}. Skipping.")
        return None

    # need one file to probe the configuration
    probe_file_path = ts_files[0]

    try:
        # Pass all 3 paths to the node script
        process_args = [
            'node',
            NODE_HELPER_SCRIPT,
            probe_file_path,  # Arg 1: Probe file
            config_file_full_path,  # Arg 2: Config file
            repo_root_path  # Arg 3: Repo root
        ]

        process = subprocess.run(
            process_args,
            capture_output=True, text=True, check=True, timeout=120  # Increased timeout
        )

        return json.loads(process.stdout)

    except subprocess.CalledProcessError as e:
        print(f"  -> Error running Node.js script: {e.stderr.strip()}")
        return None
    except json.JSONDecodeError:
        print(f"  -> Error: Node.js script did not return valid JSON.")
        return None
    except Exception as e:
        print(f"  -> An unexpected error occurred: {e}")
        return None


def calculate_strictness(config_rules):
    """Calculates strictness metrics """
    if not config_rules:
        return {'absolute_strictness': 0, 'relative_strictness': 0.0, 'total_enabled': 0}

    error_count = 0
    enabled_count = 0

    for rule_name, config in config_rules.items():
        level = None
        if isinstance(config, list) and config:
            level = config[0]
        elif isinstance(config, (str, int)):
            level = config

        if level in ('error', 2):
            error_count += 1
            enabled_count += 1
        elif level in ('warn', 1):
            enabled_count += 1

    relative_strictness = (error_count / enabled_count) if enabled_count > 0 else 0.0

    return {
        'absolute_strictness': error_count,
        'relative_strictness': relative_strictness,
        'total_enabled': enabled_count
    }


def analyze_repo(repo_url, config_file_relative_path):
    """
    Clones, installs dependencies, analyzes, and cleans up a single repository.
    """
    try:
        # 1. Clone the repo
        clone_url = repo_url if repo_url.endswith('.git') else f"{repo_url}.git"
        subprocess.run(
            ['git', 'clone', '--depth', '1', clone_url, TEMP_REPO_PATH],
            check=True, capture_output=True, timeout=300
        )

        # 2. Install dependencies (npm install)
        print("  -> Running 'npm install'...")
        try:
            subprocess.run(
                ['npm', 'install'],
                cwd=TEMP_REPO_PATH,  # Run command inside the cloned repo
                check=True,
                capture_output=True,
                timeout=300  # 5 min timeout for install
            )
            print("  -> 'npm install' complete.")
        except subprocess.CalledProcessError as e:
            print(f"  -> 'npm install' failed: {e.stderr.decode('utf-8').strip()}")
            return None  # Can't analyze if install fails
        except subprocess.TimeoutExpired:
            print(f"  -> 'npm install' timed out.")
            return None

        # 3. Get the config

        # Pass both the repo path and the relative config path
        config_rules = get_eslint_config(TEMP_REPO_PATH, config_file_relative_path)

        if config_rules is None:
            return None

        # 4. Calculate strictness
        strictness_metrics = calculate_strictness(config_rules)
        return strictness_metrics

    except subprocess.CalledProcessError as e:
        print(f"  -> Failed to clone {repo_url}: {e.stderr.decode('utf-8').strip()}")
        return None
    except subprocess.TimeoutExpired:
        print(f"  -> Timeout cloning {repo_url}.")
        return None
    finally:
        # 5. Clean up the cloned repo
        if os.path.exists(TEMP_REPO_PATH):
            shutil.rmtree(TEMP_REPO_PATH)


def main():
    print(f"Loading repositories from {INPUT_CSV}...")
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"Error: Could not find {INPUT_CSV}.")
        return

    # Column names
    URL_COLUMN = 'html_url'
    LINTER_COLUMN = 'has_eslint'
    CONFIG_PATH_COLUMN = 'eslint_config_path'

    if (URL_COLUMN not in df.columns or
            LINTER_COLUMN not in df.columns or
            CONFIG_PATH_COLUMN not in df.columns):
        print(f"Error: CSV must contain '{URL_COLUMN}', '{LINTER_COLUMN}', and '{CONFIG_PATH_COLUMN}' columns.")
        print(f"Found columns: {list(df.columns)}")
        return

    df['absolute_strictness'] = pd.NA
    df['relative_strictness'] = pd.NA
    df['total_enabled'] = pd.NA
    df['analysis_status'] = 'not_run'

    eslint_df_indices = df[df[LINTER_COLUMN] == True].index
    print(f"Found {len(eslint_df_indices)} repositories with ESLint to analyze.")

    for i, index in enumerate(eslint_df_indices):
        repo_url = df.at[index, URL_COLUMN]

        # Get the relative path to the config file
        config_path = df.at[index, CONFIG_PATH_COLUMN]

        print(f"\nAnalyzing ({i + 1}/{len(eslint_df_indices)}): {repo_url}")

        # Pass the config path to the analysis function
        metrics = analyze_repo(repo_url, config_path)

        if metrics:
            print(f"  -> Success: {metrics}")
            df.at[index, 'absolute_strictness'] = metrics['absolute_strictness']
            df.at[index, 'relative_strictness'] = metrics['relative_strictness']
            df.at[index, 'total_enabled'] = metrics['total_enabled']
            df.at[index, 'analysis_status'] = 'success'
        else:
            print(f"  -> Failed to analyze {repo_url}.")
            df.at[index, 'analysis_status'] = 'failed'

        # Save progress every 10 repos
        if (i + 1) % 10 == 0:
            print(f"\n--- Saving progress to {OUTPUT_CSV} ---")
            df.to_csv(OUTPUT_CSV, index=False)

    print(f"\nAnalysis complete. Saving final results to {OUTPUT_CSV}.")
    df.to_csv(OUTPUT_CSV, index=False)
    print("Done.")


if __name__ == "__main__":
    if os.path.exists(TEMP_REPO_PATH):
        print("Cleaning up old 'temp_repo' directory...")
        shutil.rmtree(TEMP_REPO_PATH)
    main()