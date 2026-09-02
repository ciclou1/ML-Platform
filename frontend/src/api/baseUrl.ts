export function resolveApiBaseUrl(configuredBaseUrl: string | undefined, isDevelopment: boolean): string {
  if (isDevelopment) {
    return '/api/v1'
  }
  return configuredBaseUrl ? `${configuredBaseUrl}/api/v1` : '/api/v1'
}
