export default {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '\\.(css|less|scss|sass)$': '<rootDir>/src/__mocks__/styleMock.js',
    '^d3$': '<rootDir>/src/__mocks__/d3Mock.js',
    '^plotly\\.js-dist-min$': '<rootDir>/src/__mocks__/plotlyMock.js',
    '^react-plotly\\.js$': '<rootDir>/src/__mocks__/reactPlotlyMock.js',
    '^clsx$': '<rootDir>/src/__mocks__/clsxMock.js',
    '^.*/config/constants$': '<rootDir>/src/__mocks__/constants.ts',
  },
  transform: {
    '^.+\\.(ts|tsx)$': ['ts-jest', {
      tsconfig: {
        jsx: 'react-jsx',
        esModuleInterop: true,
      },
    }],
  },
  testMatch: ['**/__tests__/**/*.{ts,tsx}', '**/*.test.{ts,tsx}'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
}
