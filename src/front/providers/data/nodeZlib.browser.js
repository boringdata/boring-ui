const unsupported = (operation) => {
  throw new Error(
    `just-bash ${operation} is unavailable in browser builds. ` +
    'The justbash backend does not support gzip/gunzip/zcat.',
  )
}

export const constants = {
  Z_BEST_COMPRESSION: 9,
  Z_BEST_SPEED: 1,
  Z_DEFAULT_COMPRESSION: -1,
}

export const gunzipSync = () => unsupported('gunzip')
export const gzipSync = () => unsupported('gzip')
