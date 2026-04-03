import axios from 'axios'

jest.mock('axios', () => ({
  create: jest.fn().mockReturnValue({
    get: jest.fn().mockResolvedValue({ data: [] }),
    post: jest.fn().mockResolvedValue({ data: {} }),
    interceptors: {
      response: { use: jest.fn() },
    },
  }),
}))

describe('api service', () => {
  it('creates axios instance', () => {
    require('../../services/api')
    expect(axios.create).toHaveBeenCalledWith(
      expect.objectContaining({
        timeout: 10000,
      })
    )
  })
})
