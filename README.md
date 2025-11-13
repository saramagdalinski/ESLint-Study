# An Empirical Study on the Efficacy of ESLint in Reducing Bugs in TypeScript

This repository contains the data collection and analysis scripts for the CMPT 479/982 project, "An Empirical Study on the Efficacy of ESLint in Reducing Bugs in TypeScript." The goal of this research is to empirically study the relationship between ESLint adoption, configuration strictness, and bug-fix activity in open-source TypeScript projects.

## 🚀 Project Goals

This project seeks to answer the following research questions:

1.  **RQ1:** How prevalent is the adoption of ESLint among open-source TypeScript Projects, and how strict are their configurations?
2.  **RQ2:** Do TypeScript projects that use ESLint exhibit lower bug-fix ratios compared to those that do not?
3.  **RQ3:** Is there a relationship between the strictness of a project's ESLint configuration and its bug-fix activity?
4.  **RQ4:** For a subset of bug-fix commits, what fraction are "linter-preventable" under a project's actual config vs. a standard config?

## 🛠️ Methodology Overview

The analysis is conducted in several phases:

1.  **Data Collection:** A Python script uses the GitHub API to find popular, non-forked TypeScript repositories. It checks for the presence of ESLint configuration files to classify them.
2.  **Strictness Analysis:** For repositories with ESLint, a Node.js helper script is used to
    parse the configuration file (including all `extends` and plugins) to get the final, "flattened" ruleset. We then calculate two metrics:
    * **Absolute Strictness:** The total number of rules configured as `"error"`.
    * **Relative Strictness:** The ratio of `"error"` rules to the total number of enabled rules.
3.  **Bug-Fix Identification:** Bug-fix commits are identified by parsing commit messages for two keywords "fix," "bug,".
4.  **Statistical Analysis:** The collected data is used to compare bug-fix ratios between projects with and without ESLint and to find correlations between strictness and bug-fix activity.
5. **Linter-Preventable Analysis:** A small selection of bug fix commits are analyzed by taking pre and post commit snapshots and marking "buggy" lines of code. Then running ESLint to see if it marks this section of code. 

## ⚙️ Setup and Installation

### 1. System Dependencies
* [Python 3.8+](https://www.python.org/)
* [Node.js v18+](https://nodejs.org/) (which includes `npm`)
* [Git](https://git-scm.com/)

### 2. Python Dependencies

# Install required Python packages
pip install pandas requests

