// Minimal ESLint flat config for Next.js 16 + TypeScript
import { createRequire } from "module";
import { fileURLToPath } from "url";
import { dirname } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const require = createRequire(import.meta.url);

const tsParser = require.resolve("@typescript-eslint/parser", {
  paths: [
    `${__dirname}/node_modules/.pnpm/@typescript-eslint+parser@8.59.4_eslint@9.39.4_jiti@2.7.0__typescript@6.0.3/node_modules`,
  ],
});

const parser = require(tsParser);

/** @type {import("eslint").Linter.Config[]} */
const config = [
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "dist/**",
      "eslint.config.mjs",
      "vitest.config.ts",
      "next.config.ts",
      "postcss.config.mjs",
    ],
  },
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
    rules: {
      "no-unused-vars": "off",
    },
  },
];

export default config;
