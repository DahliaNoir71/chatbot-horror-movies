let loginUrl = '/login'

export function setLoginUrl(url: string): void {
  loginUrl = url
}

export function redirectToLogin(): void {
  window.location.href = loginUrl
}
