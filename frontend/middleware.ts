import { NextRequest, NextResponse } from "next/server";

// Guard based on the session cookie's presence. Validity is checked by the
// backend via /api/me; pages redirect to /login if the session is stale.
export function middleware(req: NextRequest) {
  const hasSession = req.cookies.has("session");
  const { pathname } = req.nextUrl;

  if (pathname === "/login") {
    return hasSession
      ? NextResponse.redirect(new URL("/", req.url))
      : NextResponse.next();
  }

  return hasSession
    ? NextResponse.next()
    : NextResponse.redirect(new URL("/login", req.url));
}

export const config = {
  matcher: ["/((?!_next|api|favicon.ico).*)"],
};
