// Batch government-scheme matching run over onboarded users.
import { withTransaction } from "../db.js";
import { matchSchemes } from "./schemeMatcher.js";

export async function runSchemeMatching() {
  return withTransaction(async (tx) => {
    const users = await tx.query("SELECT * FROM users WHERE onboarding_complete = 1");
    let created = 0;
    for (const user of users) created += await matchSchemes(user, tx);
    return { users_evaluated: users.length, matches_created: created };
  });
}
