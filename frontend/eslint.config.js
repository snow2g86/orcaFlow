// ESLint flat config — OrcaFlow frontend (Vite + React + TypeScript)
// conventions.md §1, §3.4, §6.4 의 규칙을 코드 레벨로 강제한다.

import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import importPlugin from 'eslint-plugin-import'
import boundaries from 'eslint-plugin-boundaries'
import prettier from 'eslint-config-prettier'

export default tseslint.config(
  { ignores: ['dist', 'node_modules', '.vite', 'coverage', 'eslint.config.js', 'vite.config.ts', 'vitest.config.ts'] },

  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,

  {
    files: ['**/*.{ts,tsx}'],
    plugins: {
      react,
      'react-hooks': reactHooks,
      import: importPlugin,
      boundaries,
    },
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.json', './tsconfig.node.json'],
        tsconfigRootDir: import.meta.dirname,
        ecmaVersion: 2023,
        sourceType: 'module',
      },
    },
    settings: {
      react: { version: 'detect' },
      'import/resolver': {
        typescript: { project: './tsconfig.json' },
      },
      'boundaries/elements': [
        { type: 'components-ui', pattern: 'src/components/ui/*' },
        { type: 'components', pattern: 'src/components/*' },
        { type: 'features', pattern: 'src/features/*', capture: ['feature'] },
        { type: 'stores', pattern: 'src/stores/*' },
        { type: 'hooks', pattern: 'src/hooks/*' },
        { type: 'lib-api', pattern: 'src/lib/api/*' },
        { type: 'lib-ipc', pattern: 'src/lib/ipc/*' },
        { type: 'lib-utils', pattern: 'src/lib/utils/*' },
        { type: 'types', pattern: 'src/types/*' },
        { type: 'styles', pattern: 'src/styles/*' },
      ],
    },
    rules: {
      // ---- TypeScript 엄격성 ----
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/consistent-type-imports': ['error', { prefer: 'type-imports' }],
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': 'error',

      // ---- React ----
      'react/jsx-uses-react': 'off',
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',

      // ---- import 순서 (conventions.md §3.5) ----
      'import/order': [
        'error',
        {
          groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index', 'type'],
          pathGroups: [{ pattern: '@/**', group: 'internal', position: 'before' }],
          pathGroupsExcludedImportTypes: ['builtin'],
          alphabetize: { order: 'asc', caseInsensitive: true },
          'newlines-between': 'always',
        },
      ],
      'import/no-default-export': 'off',

      // ---- 경계 규칙 (conventions.md §6.4) ----
      'boundaries/element-types': [
        'error',
        {
          default: 'disallow',
          rules: [
            // components/ui 는 순수 UI (비즈니스/스토어/IPC 금지)
            {
              from: ['components-ui'],
              allow: ['components-ui', 'lib-utils', 'types', 'styles'],
            },
            // components 공용은 ui + lib-utils + types
            {
              from: ['components'],
              allow: ['components', 'components-ui', 'hooks', 'lib-utils', 'types', 'styles'],
            },
            // features 는 자기 자신 + 공용 요소만
            {
              from: ['features'],
              allow: [
                ['features', { feature: '${from.feature}' }],
                'components',
                'components-ui',
                'hooks',
                'stores',
                'lib-api',
                'lib-ipc',
                'lib-utils',
                'types',
                'styles',
              ],
            },
            { from: ['hooks'], allow: ['hooks', 'stores', 'lib-api', 'lib-utils', 'types'] },
            { from: ['stores'], allow: ['stores', 'lib-api', 'lib-utils', 'types'] },
            { from: ['lib-api'], allow: ['lib-api', 'lib-ipc', 'lib-utils', 'types'] },
            { from: ['lib-ipc'], allow: ['lib-ipc', 'lib-utils', 'types'] },
            { from: ['lib-utils'], allow: ['lib-utils', 'types'] },
            { from: ['types'], allow: ['types'] },
          ],
        },
      ],

      // 컴포넌트에서 Tauri IPC 직접 호출 금지 (conventions.md §6.4)
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@tauri-apps/api/*'],
              message:
                'Tauri API는 src/lib/api 또는 src/lib/ipc 를 통해서만 사용하세요 (conventions §6.4).',
            },
            {
              group: ['src/features/*/*'],
              message: 'feature 내부 파일 직접 import 금지 — 배럴(index.ts)만 사용.',
            },
          ],
        },
      ],
    },
  },

  // lib/api, lib/ipc 는 Tauri API 직접 호출 허용
  {
    files: ['src/lib/api/**/*.{ts,tsx}', 'src/lib/ipc/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': 'off',
    },
  },

  prettier,
)
