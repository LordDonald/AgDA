import {
  NextResponse,
} from "next/server";

import {
  getAgdaApiUrl,
} from "@/lib/server-config";


export async function GET() {
  try {
    const apiUrl =
      getAgdaApiUrl();

    const response =
      await fetch(
        `${apiUrl}/v1/health`,
        {
          cache: "no-store",
        }
      );

    const payload =
      await response.json();

    return NextResponse.json(
      payload,
      {
        status:
          response.status,
      }
    );
  } catch (error) {
    console.error(
      "AgDA health check failed:",
      error
    );

    return NextResponse.json(
      {
        status:
          "offline",
        ready:
          false,
      },
      {
        status: 503,
      }
    );
  }
}