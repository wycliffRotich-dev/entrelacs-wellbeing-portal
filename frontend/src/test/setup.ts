import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { clearToken } from "../session";

afterEach(() => {
  cleanup();
  clearToken();
  sessionStorage.clear();
});
