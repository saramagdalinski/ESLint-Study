// @ts-check

// TODO: FIGURE OUT WHAT CONFIGURATION WE WANT FOR OUR PROJECT

import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  // 1. All of ESLint's recommended rules
  eslint.configs.recommended,

  // 2. All of TypeScript-ESLint's "strict" rules
  // (requires type info, but we'll have it now!)
  ...tseslint.configs.strictTypeChecked,

  // 3. All of TypeScript-ESLint's "stylistic" rules
  // (also requires type info)
  ...tseslint.configs.stylisticTypeChecked,

  // 4. Configure the parser
  {
    files: ['**/*.ts', '**/*.tsx'],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        // This is the KEY!
        // It tells ESLint to find the nearest tsconfig.json
        // and use it, giving us full type-aware linting.
        project: true,
      },
    },
    rules: {
      // You can add any extra "super-strict" rules here
      // For example, turn 'eqeqeq' into a hard error
      'eqeqeq': 'error',
    }
  }
);