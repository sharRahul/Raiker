export function isLoopbackHost(hostname: string): boolean {
  return ["localhost", "127.0.0.1", "::1"].includes(hostname);
}
