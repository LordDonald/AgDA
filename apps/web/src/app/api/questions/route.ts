import {
  NextRequest,
  NextResponse,
} from "next/server";

import {
  getAgdaApiUrl,
} from "@/lib/server-config";


export async function POST(
  request: NextRequest
) {
  try {
    const body =
      await request.json();

    const apiUrl =
      getAgdaApiUrl();

    const requestId =
      request.headers.get(
        "X-Request-ID"
      );

    const headers:
      Record<string, string> = {
        "Content-Type":
          "application/json",
      };

    if (requestId) {
      headers["X-Request-ID"] =
        requestId;
    }

    const response =
      await fetch(
        `${apiUrl}/v1/questions`,
        {
          method: "POST",
          headers,
          body:
            JSON.stringify(body),
          cache: "no-store",
        }
      );

    const payload =
      await response.json();

    const backendRequestId =
      response.headers.get(
        "X-Request-ID"
      );

    const responseHeaders:
      Record<string, string> = {};

    if (backendRequestId) {
      responseHeaders[
        "X-Request-ID"
      ] = backendRequestId;
    }

    return NextResponse.json(
      payload,
      {
        status:
          response.status,
        headers:
          responseHeaders,
      }
    );

  } catch (error) {
    console.error(
      "AgDA backend request failed:",
      error
    );

    return NextResponse.json(
      {
        status:
          "system_error",
        answer_text:
          "AgDA could not reach the analytical service.",
      },
      {
        status: 503,
      }
    );
  }
}