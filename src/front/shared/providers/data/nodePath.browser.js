export function join(...parts) {
  return parts.filter(Boolean).join('/')
}

export default {
  join,
}
