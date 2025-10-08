module.exports = {
  root: true,
  env: { browser: true, es2021: true, node: true },
  extends: [
    "eslint:recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
    "plugin:jsx-a11y/recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:@typescript-eslint/recommended-requiring-type-checking",
  ],
  ignorePatterns: ["dist", ".eslintrc.cjs"],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: {
      jsx: true,
    },
    project: ["./tsconfig.json", "./tsconfig.node.json"],
    tsconfigRootDir: __dirname,
  },
  plugins: [
    "react",
    "react-hooks",
    "jsx-a11y",
    "react-refresh",
    "@typescript-eslint",
  ],
  settings: {
    react: {
      version: "detect", // Automatically detect React version
    },
  },
  rules: {
    // React rules
    "react/react-in-jsx-scope": "off", // Not needed in React 18+
    "react/prop-types": "off", // Using TypeScript for prop validation
    "react/jsx-key": "error", // Enforce keys in lists

    // React Hooks rules
    "react-hooks/rules-of-hooks": "error", // Enforce Rules of Hooks
    "react-hooks/exhaustive-deps": "warn", // Warn about missing dependencies

    // React Refresh
    "react-refresh/only-export-components": [
      "warn",
      { allowConstantExport: true },
    ],

    // TypeScript rules
    "@typescript-eslint/no-non-null-assertion": "error",
    "@typescript-eslint/no-unused-vars": "error",
    "@typescript-eslint/no-explicit-any": "warn",
    "@typescript-eslint/no-unsafe-assignment": "warn",
    "@typescript-eslint/no-unsafe-member-access": "warn",
    "@typescript-eslint/no-unsafe-call": "warn",
    "@typescript-eslint/no-unsafe-return": "warn",
  },
};
