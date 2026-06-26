/**
 * Thin fetch wrapper with timeout + retry on transient errors.
 *
 * The Pi listens on plain HTTP under application-layer encryption (per
 * spec §10), so this client doesn't enforce HTTPS. The envelope layer
 * provides confidentiality and integrity.
 */

import type { ApiErrorBody } from '../../types';

export interface ApiClientOptions {
  timeoutMs?: number;
  retryAttempts?: number;
  /** Override fetch (Jest passes a mock here). */
  fetchImpl?: typeof fetch;
}

export interface ApiRequest {
  method: 'GET' | 'POST' | 'PATCH';
  path: string;
  body?: unknown;
  headers?: Record<string, string>;
}

export interface ApiResponse<T> {
  status: number;
  body: T;
}

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message?: string) {
    super(message ?? `${status} ${code}`);
    this.status = status;
    this.code = code;
  }
}

export interface ApiClient {
  request<T>(input: ApiRequest): Promise<ApiResponse<T>>;
}

const DEFAULT_TIMEOUT_MS = 8_000;
const DEFAULT_RETRIES = 1;

const TRANSIENT_STATUSES = new Set([502, 503, 504]);

export const createApiClient = (
  baseUrl: string,
  options: ApiClientOptions = {},
): ApiClient => {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const retries = options.retryAttempts ?? DEFAULT_RETRIES;
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  if (typeof fetchImpl !== 'function') {
    throw new Error('createApiClient: fetch is not available');
  }

  const trimmedBase = baseUrl.replace(/\/+$/, '');

  const doRequest = async <T>(req: ApiRequest, attempt: number): Promise<ApiResponse<T>> => {
    const url = `${trimmedBase}${req.path}`;
    const controller = new AbortController();
    const timer: ReturnType<typeof setTimeout> = setTimeout(
      () => controller.abort(),
      timeoutMs,
    );

    try {
      const response = await fetchImpl(url, {
        method: req.method,
        headers: {
          'Content-Type': 'application/json',
          ...req.headers,
        },
        body: req.body === undefined ? undefined : JSON.stringify(req.body),
        signal: controller.signal,
      });

      // Read body once; both success and error paths need it.
      const text = await response.text();
      let parsed: unknown = null;
      if (text.length > 0) {
        try {
          parsed = JSON.parse(text);
        } catch {
          // Non-JSON body — return as string.
          parsed = text;
        }
      }

      if (!response.ok) {
        const error = parsed as ApiErrorBody | null;
        const code = error?.error?.code ?? `http_${response.status}`;
        const message = error?.error?.message ?? `HTTP ${response.status}`;
        // Retry transient 5xx if attempts remain.
        if (TRANSIENT_STATUSES.has(response.status) && attempt < retries) {
          return doRequest<T>(req, attempt + 1);
        }
        throw new ApiError(response.status, code, message);
      }

      return { status: response.status, body: parsed as T };
    } catch (err) {
      if (err instanceof ApiError) throw err;
      if (attempt < retries) {
        return doRequest<T>(req, attempt + 1);
      }
      const message = err instanceof Error ? err.message : 'network error';
      throw new ApiError(0, 'network_error', message);
    } finally {
      clearTimeout(timer);
    }
  };

  return {
    request: <T>(req: ApiRequest) => doRequest<T>(req, 0),
  };
};
