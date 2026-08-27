export interface Env {
  ALLOWED_ORIGIN: string
  GITHUB_REPO: string
  SKIP_FIRESTORE?: string
  GITHUB_PAT?: string
  FIREBASE_CREDENTIALS?: string
  TIKTOK_CLIENT_KEY?: string
  TIKTOK_CLIENT_SECRET?: string
  TIKTOK_REDIRECT_URI?: string
  ASSETS?: {
    fetch(request: Request): Promise<Response>
  }
}

export interface ServiceAccount {
  type: string
  project_id: string
  private_key_id: string
  private_key: string
  client_email: string
  client_id: string
  auth_uri: string
  token_uri: string
  auth_provider_x509_cert_url: string
  client_x509_cert_url: string
}

export interface ClientPayload {
  userId: string
  topic: string
  platform: string
  documentId?: string
}
