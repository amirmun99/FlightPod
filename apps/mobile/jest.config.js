/**
 * Jest config. We deliberately don't use ``jest-expo`` for the pure-JS
 * test suite — pulling in the full RN preset adds ~30s of setup for tests
 * that only exercise crypto and parsers. The crypto modules don't import
 * any Expo or RN modules, so plain ``ts-jest`` is enough.
 *
 * Phase 9/10 may add a separate ``jest-expo`` config for component tests.
 */

/** @type {import('jest').Config} */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: ['**/__tests__/**/*.test.ts', '**/?(*.)+(spec|test).ts'],
  testPathIgnorePatterns: ['/node_modules/', '/ios/', '/android/'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'json'],
  transform: {
    '^.+\\.tsx?$': ['ts-jest', { tsconfig: { jsx: 'react-native' } }],
  },
};
