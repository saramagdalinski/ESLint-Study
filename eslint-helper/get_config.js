// get_config.js
const path = require('path');


// This script now takes THREE arguments
const probeFilePath = process.argv[2];
const configFilePath = process.argv[3];
const repoRoot = process.argv[4];

if (!probeFilePath || !configFilePath || !repoRoot) {
  console.error('Error: Missing arguments. Requires: probe_file_path, config_file_path, repo_root');
  process.exit(1);
}


// Resolve all paths to be absolute
const absoluteProbePath = path.resolve(probeFilePath);
const absoluteConfigPath = path.resolve(configFilePath);
const absoluteRepoRoot = path.resolve(repoRoot);



// load the ESLint from the repo's own node_modules
const localEslintPath = path.join(absoluteRepoRoot, 'node_modules', 'eslint');
let ESLint;

try {
  ESLint = require(localEslintPath).ESLint;
} catch (e) {
  console.error(`Error: Could not load local ESLint from ${localEslintPath}.`);
  console.error('Did "npm install" fail in the Python script?');
  console.error(e.message);
  process.exit(1);
}


// We use the config file's directory as the 'cwd'
// This tells ESLint where to start looking for configs
const configDir = path.dirname(absoluteConfigPath);

(async () => {
  try {
    const eslint = new ESLint({
      cwd: configDir,


      overrideConfigFile: absoluteConfigPath
    });

    // calculate the config for our "probe" file
    const config = await eslint.calculateConfigForFile(absoluteProbePath);

    // Print the full configuration as a JSON string to stdout.
    console.log(JSON.stringify(config.rules, null, 2));

  } catch (e) {
    console.error(`Error calculating ESLint config: ${e.message}`);
    process.exit(1);
  }
})();