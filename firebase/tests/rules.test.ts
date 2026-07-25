// SPDX-License-Identifier: Apache-2.0
// Prove the Firestore security rules that protect user content (chat-session
// message privacy). The users/{uid}/answers consent gate is not on this branch
// — it returns with the party-matcher feature that actually writes a user's own
// political answers.
//
// Python firebase-admin bypasses security rules — this test MUST be JS/TS.
// projectId must start with "demo-" for emulator-only isolation.
//
// Requires Firestore emulator on port 8081 (avoids clash with FastAPI on 8080).

import {
  initializeTestEnvironment,
  assertFails,
  assertSucceeds,
  type RulesTestEnvironment,
} from "@firebase/rules-unit-testing";
import { readFileSync } from "fs";
import { describe, it, beforeAll, afterAll } from "vitest";
import { fileURLToPath } from "url";
import { resolve, dirname } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

let testEnv: RulesTestEnvironment;

beforeAll(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: "demo-wahl-chat",
    firestore: {
      rules: readFileSync(resolve(__dirname, "../firestore.rules"), "utf8"),
      host: "localhost",
      port: 8081,
    },
  });
});

afterAll(async () => {
  await testEnv.cleanup();
});

describe("CR-03 — chat_sessions/{id}/messages access is scoped to owner/public", () => {
  it("allows the session owner to read their private session's messages (assertSucceeds)", async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx
        .firestore()
        .doc("chat_sessions/s-private")
        .set({ user_id: "owner1", is_public: false });
      await ctx
        .firestore()
        .doc("chat_sessions/s-private/messages/m1")
        .set({ role: "user", content: "secret" });
    });

    const owner = testEnv.authenticatedContext("owner1");
    await assertSucceeds(
      owner.firestore().doc("chat_sessions/s-private/messages/m1").get()
    );
  });

  it("rejects a non-owner reading a private session's messages (assertFails)", async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx
        .firestore()
        .doc("chat_sessions/s-private2")
        .set({ user_id: "owner2", is_public: false });
      await ctx
        .firestore()
        .doc("chat_sessions/s-private2/messages/m1")
        .set({ role: "user", content: "secret" });
    });

    const intruder = testEnv.authenticatedContext("intruder");
    await assertFails(
      intruder.firestore().doc("chat_sessions/s-private2/messages/m1").get()
    );
  });

  it("rejects an unauthenticated read of a private session's messages (assertFails)", async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx
        .firestore()
        .doc("chat_sessions/s-private3")
        .set({ user_id: "owner3", is_public: false });
      await ctx
        .firestore()
        .doc("chat_sessions/s-private3/messages/m1")
        .set({ role: "user", content: "secret" });
    });

    const anon = testEnv.unauthenticatedContext();
    await assertFails(
      anon.firestore().doc("chat_sessions/s-private3/messages/m1").get()
    );
  });

  it("allows anyone to read a PUBLIC session's messages (assertSucceeds)", async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx
        .firestore()
        .doc("chat_sessions/s-public")
        .set({ user_id: "owner4", is_public: true });
      await ctx
        .firestore()
        .doc("chat_sessions/s-public/messages/m1")
        .set({ role: "user", content: "hello" });
    });

    const anon = testEnv.unauthenticatedContext();
    await assertSucceeds(
      anon.firestore().doc("chat_sessions/s-public/messages/m1").get()
    );
  });

  it("rejects an unauthenticated create of a session's messages (assertFails)", async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx
        .firestore()
        .doc("chat_sessions/s-public2")
        .set({ user_id: "owner5", is_public: true });
    });

    const anon = testEnv.unauthenticatedContext();
    await assertFails(
      anon
        .firestore()
        .doc("chat_sessions/s-public2/messages/m1")
        .set({ role: "user", content: "spam" })
    );
  });

  // Being AUTHENTICATED is not enough — only the session owner may write messages.
  it("rejects an authenticated non-owner writing to another user's session messages (assertFails)", async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx
        .firestore()
        .doc("chat_sessions/s-private4")
        .set({ user_id: "owner6", is_public: false });
    });

    const intruder = testEnv.authenticatedContext("intruder2");
    await assertFails(
      intruder
        .firestore()
        .doc("chat_sessions/s-private4/messages/m1")
        .set({ role: "user", content: "injected" })
    );
  });
});
