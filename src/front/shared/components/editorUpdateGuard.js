export function consumeInitialUpdateGuard(guardRef) {
  if (guardRef?.current) {
    guardRef.current = false
    return true
  }
  return false
}
