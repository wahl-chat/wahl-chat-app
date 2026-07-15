// SPDX-License-Identifier: Apache-2.0
// SC3 / DATA-05: Prove the GDPR Art. 9 consent gate in Firestore rules.
//
// Pitfall 4: Python firebase-admin bypasses security rules — this test MUST be JS/TS.
// Pitfall 7: projectId must start with "demo-" for emulator-only isolation.
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

describe("GDPR Art. 9 wall — users/{uid}/answers consent gate (SC3/DATA-05)", () => {
  it("rejects answers write when consent.political_data is absent (assertFails)", async () => {
    // Seed a user doc WITHOUT consent using Admin-equivalent bypass
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx
        .firestore()
        .doc("users/alice")
        .set({ email: "alice@example.com" });
    });

    // Authenticated as alice, but no consent.political_data on parent doc
    const alice = testEnv.authenticatedContext("alice");
    await assertFails(
      alice
        .firestore()
        .doc("users/alice/answers/a1")
        .set({ stance: "yes" })
    );
  });

  it("allows answers write when consent.political_data === true (assertSucceeds)", async () => {
    // Seed a user doc WITH explicit political consent
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx
        .firestore()
        .doc("users/bob")
        .set({ email: "bob@example.com", consent: { political_data: true } });
    });

    // Authenticated as bob, consent granted
    const bob = testEnv.authenticatedContext("bob");
    await assertSucceeds(
      bob
        .firestore()
        .doc("users/bob/answers/a1")
        .set({ stance: "yes" })
    );
  });

  // CR-02: GDPR Art. 17 — erasure must be allowed even after consent withdrawal.
  it("allows the owner to DELETE their answer even when consent is absent/false (assertSucceeds)", async () => {
    // Seed an answer + a user doc WITHOUT political consent, bypassing rules.
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx
        .firestore()
        .doc("users/carol")
        .set({ email: "carol@example.com", consent: { political_data: false } });
      await ctx
        .firestore()
        .doc("users/carol/answers/a1")
        .set({ stance: "yes" });
    });

    // Authenticated as carol, consent revoked — erasure must still succeed.
    const carol = testEnv.authenticatedContext("carol");
    await assertSucceeds(
      carol.firestore().doc("users/carol/answers/a1").delete()
    );
  });

  it("rejects DELETE of another user's answer (assertFails)", async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx
        .firestore()
        .doc("users/dave/answers/a1")
        .set({ stance: "yes" });
    });

    const mallory = testEnv.authenticatedContext("mallory");
    await assertFails(
      mallory.firestore().doc("users/dave/answers/a1").delete()
    );
  });

  // G15: answers are special-category data — no cross-user READ, ever.
  it("rejects a cross-user READ of another user's answer (assertFails)", async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx
        .firestore()
        .doc("users/erin")
        .set({ email: "erin@example.com", consent: { political_data: true } });
      await ctx
        .firestore()
        .doc("users/erin/answers/a1")
        .set({ stance: "yes" });
    });

    const snoop = testEnv.authenticatedContext("snoop");
    await assertFails(
      snoop.firestore().doc("users/erin/answers/a1").get()
    );
  });

  // G15: consent explicitly WITHDRAWN (false) must deny create just like absent consent.
  it("rejects answers create when consent.political_data === false (assertFails)", async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx
        .firestore()
        .doc("users/frank")
        .set({ email: "frank@example.com", consent: { political_data: false } });
    });

    // Authenticated as frank himself — consent revoked, so create must fail.
    const frank = testEnv.authenticatedContext("frank");
    await assertFails(
      frank
        .firestore()
        .doc("users/frank/answers/a1")
        .set({ stance: "yes" })
    );
  });
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

  // G15: being AUTHENTICATED is not enough — only the session owner may write messages.
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
