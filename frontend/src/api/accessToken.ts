/** 给无法携带 Authorization 头的文件流 URL（<img>/window.open）附加 access_token 查询参数。 */

export function appendAccessToken(url: string): string {
  let token = ''
  try {
    token = localStorage.getItem('auth-token') || ''
  } catch {
    token = ''
  }
  if (!token) {
    return url
  }
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}access_token=${encodeURIComponent(token)}`
}
