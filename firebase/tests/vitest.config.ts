// SPDX-FileCopyrightText: 2026 wahl.chat
//
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["**/*.test.ts"],
    testTimeout: 30000,
  },
});
