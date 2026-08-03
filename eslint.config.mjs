import js from "@eslint/js";
import globals from "globals";

export default [
    js.configs.recommended,
    {
        files: ["src/**/*.js"],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: "module",
            globals: globals.browser,
        },
        rules: {
            "no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
            "no-console": ["error", { allow: ["warn", "error"] }],
            eqeqeq: ["error", "smart"],
            "prefer-const": "error",
        },
    },
    {
        files: ["scripts/**/*.mjs"],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: "module",
            globals: globals.node,
        },
    },
];
