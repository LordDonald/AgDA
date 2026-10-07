import {
  timingSafeEqual,
} from "node:crypto";

import {
  NextRequest,
  NextResponse,
} from "next/server";

import {
  getAgdaApiUrl,
} from "@/lib/server-config";


const allowedResources = new Set([
  "overview",
  "daily",
  "metrics",
  "statuses",
  "feedback-reasons",
]);


function tokensMatch(
  supplied: string | null,
  configured: string | undefined
): boolean {

  if (
    !supplied
    ||
    !configured
  ) {
    return false;
  }


  const suppliedBuffer =
    Buffer.from(
      supplied,
      "utf8"
    );

  const configuredBuffer =
    Buffer.from(
      configured,
      "utf8"
    );


  if (
    suppliedBuffer.length
    !== configuredBuffer.length
  ) {
    return false;
  }


  return timingSafeEqual(
    suppliedBuffer,
    configuredBuffer
  );
}


export async function GET(
  request: NextRequest
) {

  const dashboardToken =
    request.headers.get(
      "X-AgDA-Dashboard-Token"
    );

  const configuredDashboardToken =
    process.env
      .AGDA_INTERNAL_DASHBOARD_TOKEN;


  if (
    !tokensMatch(
      dashboardToken,
      configuredDashboardToken
    )
  ) {

    return NextResponse.json(
      {
        detail:
          "Unauthorized.",
      },
      {
        status: 401,
      }
    );

  }


  const backendToken =
    process.env
      .AGDA_INTERNAL_ANALYTICS_TOKEN;


  if (!backendToken) {

    return NextResponse.json(
      {
        detail:
          "Internal analytics proxy " +
          "is not configured.",
      },
      {
        status: 503,
      }
    );

  }


  const resource =
    request.nextUrl.searchParams.get(
      "resource"
    );


  if (
    !resource
    ||
    !allowedResources.has(
      resource
    )
  ) {

    return NextResponse.json(
      {
        detail:
          "Unsupported analytics resource.",
      },
      {
        status: 400,
      }
    );

  }


  try {

    const apiUrl =
      getAgdaApiUrl();


    const response =
      await fetch(
        (
          `${apiUrl}` +
          `/v1/internal/analytics/${resource}`
        ),
        {
          headers: {
            "X-AgDA-Internal-Token":
              backendToken,
          },

          cache:
            "no-store",
        }
      );


    const payload =
      await response.json();


    return NextResponse.json(
      payload,
      {
        status:
          response.status,

        headers: {
          "Cache-Control":
            "no-store",
        },
      }
    );

  } catch (error) {

    console.error(
      "Internal analytics proxy failed:",
      error instanceof Error
        ? error.name
        : "UnknownError"
    );


    return NextResponse.json(
      {
        detail:
          "Internal analytics is " +
          "temporarily unavailable.",
      },
      {
        status: 503,
      }
    );

  }
}
