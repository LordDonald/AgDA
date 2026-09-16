const LOCAL_AGDA_API_URL =
  "http://127.0.0.1:8000";


function normalizeApiUrl(
  value: string
): string {
  const url = new URL(value);

  if (
    url.protocol !== "http:" &&
    url.protocol !== "https:"
  ) {
    throw new Error(
      "AGDA_API_URL must use http or https."
    );
  }

  return url
    .toString()
    .replace(/\/+$/, "");
}


export function getAgdaApiUrl(): string {
  const configuredUrl =
    process.env.AGDA_API_URL?.trim();

  if (configuredUrl) {
    return normalizeApiUrl(
      configuredUrl
    );
  }

  if (
    process.env.NODE_ENV === "production"
  ) {
    throw new Error(
      "AGDA_API_URL must be configured in production."
    );
  }

  return LOCAL_AGDA_API_URL;
}