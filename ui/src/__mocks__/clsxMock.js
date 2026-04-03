// clsx mock for Jest (CommonJS compatible)
function clsx(...args) {
  return args
    .filter(Boolean)
    .map((arg) => {
      if (typeof arg === 'string') return arg
      if (typeof arg === 'object' && arg !== null) {
        return Object.entries(arg)
          .filter(([, v]) => v)
          .map(([k]) => k)
          .join(' ')
      }
      return ''
    })
    .join(' ')
    .trim()
}

module.exports = clsx
module.exports.default = clsx
module.exports.clsx = clsx
