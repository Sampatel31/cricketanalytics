import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import WarRoom from '../WarRoom'

global.WebSocket = jest.fn().mockImplementation(() => ({
  onopen: null,
  onmessage: null,
  onerror: null,
  onclose: null,
  send: jest.fn(),
  close: jest.fn(),
  readyState: 1,
  OPEN: 1,
})) as unknown as typeof WebSocket

global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}))

jest.mock('axios', () => ({
  create: () => ({
    get: jest.fn().mockResolvedValue({ data: [] }),
    post: jest.fn().mockResolvedValue({ data: {} }),
    interceptors: {
      response: { use: jest.fn() },
    },
  }),
}))

describe('WarRoom', () => {
  it('renders without crashing', () => {
    render(<WarRoom />)
    expect(screen.getByText('War Room')).toBeInTheDocument()
  })

  it('renders all panel headings', () => {
    render(<WarRoom />)
    expect(screen.getByText(/Galaxy View/i)).toBeInTheDocument()
    expect(screen.getByText(/Squad Builder/i)).toBeInTheDocument()
    expect(screen.getByText(/Alerts Feed/i)).toBeInTheDocument()
  })
})
