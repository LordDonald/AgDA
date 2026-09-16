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

    const response =
      await fetch(
        `${apiUrl}/v1/questions`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body:
            JSON.stringify(body),
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