import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', 'dist-mock', 'playwright-report', 'test-results', 'src/api/generated/schema.d.ts']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // `const { dropped, ...kept } = value` names what it leaves out.
      '@typescript-eslint/no-unused-vars': ['error', { ignoreRestSiblings: true }],
    },
  },
  {
    // §12: the app reaches the server through src/api/ only, and never imports the mocks (decision
    // 11: app/boot.tsx loads them with a dynamic import that a production build drops). Tests may.
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/api/**', 'src/test/**', 'src/**/*.test.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        { patterns: [{ group: ['@/api/mocks/*', '**/api/mocks/*'], message: 'The mocks load only through app/boot.tsx (decision 11).' }] },
      ],
      'no-restricted-globals': [
        'error',
        { name: 'fetch', message: 'Requests go through src/api/rest.ts (§12).' },
        { name: 'WebSocket', message: 'The socket is src/api/live-client.ts (§12).' },
      ],
    },
  },
])
