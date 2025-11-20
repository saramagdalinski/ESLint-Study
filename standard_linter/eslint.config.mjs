import tseslint from "typescript-eslint";
import globals from "globals";

export default tseslint.config(
  { ignores: ["**/node_modules/", "**/dist/"] },

  // Strict Configuration for TypeScript projects
  ...tseslint.configs.strict,

  // Stylistic Configuration for TypeScript projects
  ...tseslint.configs.stylistic,

  // Configuration for TypeScript files
  {
    files: ["**/*.ts", "**/*.tsx", "**/*.mts", "**/*.cts"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  }
);