"""Policy / PolicyRule repository."""

from __future__ import annotations

from typing import Any

import aiosqlite

from ...schema.policy import Policy, PolicyRule
from ._base import BaseRepository, json_dumps, json_loads_or_none

__all__ = ["PoliciesRepository"]


class PoliciesRepository(BaseRepository):
    async def upsert(self, policy: Policy, *, yaml: str) -> None:
        async with self._db.connect() as conn:
            await conn.execute(
                """
                INSERT INTO policies (id, name, mode, yaml, require_dry_run_for_json,
                                      auto_approve_reversible)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    mode=excluded.mode,
                    yaml=excluded.yaml,
                    require_dry_run_for_json=excluded.require_dry_run_for_json,
                    auto_approve_reversible=excluded.auto_approve_reversible;
                """,
                (
                    policy.id,
                    policy.name,
                    policy.mode,
                    yaml,
                    json_dumps(policy.require_dry_run_for) if policy.require_dry_run_for else None,
                    int(policy.auto_approve_reversible),
                ),
            )
            # rules 전체 교체
            await conn.execute("DELETE FROM policy_rules WHERE policy_id = ?;", (policy.id,))
            for rule in policy.rules:
                await conn.execute(
                    """
                    INSERT INTO policy_rules (id, policy_id, priority, scope, matcher,
                                              effect, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        rule.id,
                        policy.id,
                        rule.priority,
                        rule.scope,
                        rule.matcher,
                        rule.effect,
                        rule.reason,
                    ),
                )
            await conn.commit()

    async def get(self, policy_id: str) -> Policy | None:
        async with self._db.connect() as conn:
            async with conn.execute("SELECT * FROM policies WHERE id = ?;", (policy_id,)) as cursor:
                prow = await cursor.fetchone()
            if prow is None:
                return None
            async with conn.execute(
                "SELECT * FROM policy_rules WHERE policy_id = ? ORDER BY priority;",
                (policy_id,),
            ) as cursor:
                rule_rows = list(await cursor.fetchall())
        return _row_to_policy(prow, rule_rows)

    async def list_all(self) -> list[Policy]:
        async with self._db.connect() as conn:
            async with conn.execute("SELECT * FROM policies ORDER BY name;") as cursor:
                prows = list(await cursor.fetchall())
            results: list[Policy] = []
            for prow in prows:
                async with conn.execute(
                    "SELECT * FROM policy_rules WHERE policy_id = ? ORDER BY priority;",
                    (prow["id"],),
                ) as cursor:
                    rule_rows = list(await cursor.fetchall())
                results.append(_row_to_policy(prow, rule_rows))
        return results


def _row_to_policy(prow: aiosqlite.Row, rule_rows: list[aiosqlite.Row]) -> Policy:
    rules: list[PolicyRule] = [
        PolicyRule(
            id=str(r["id"]),
            policy_id=str(r["policy_id"]),
            priority=int(r["priority"]),
            scope=str(r["scope"]),  # type: ignore[arg-type]
            matcher=str(r["matcher"]),
            effect=str(r["effect"]),  # type: ignore[arg-type]
            reason=(str(r["reason"]) if r["reason"] else None),
        )
        for r in rule_rows
    ]
    require_dry_run: Any = json_loads_or_none(prow["require_dry_run_for_json"]) or []
    return Policy(
        id=str(prow["id"]),
        name=str(prow["name"]),
        mode=str(prow["mode"]),  # type: ignore[arg-type]
        rules=rules,
        require_dry_run_for=require_dry_run,
        auto_approve_reversible=bool(prow["auto_approve_reversible"]),
    )
