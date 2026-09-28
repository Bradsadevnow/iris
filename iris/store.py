"""Transactional persistence for the Halcyon server UI.

SQLite is authoritative. JSON files are compatibility projections written only
after a successful state transaction.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .graph import edge_id, empty_world, normalize_world, slug


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class Store:
    def __init__(self, path: str | Path, state_dir: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA synchronous = FULL")
        return db

    @staticmethod
    def _migrate_lore_provenance(db: sqlite3.Connection) -> None:
        """Generalize legacy turn-only lore provenance without losing revisions."""
        columns = {row[1] for row in db.execute("PRAGMA table_info(imagination_lore)")}
        if "created_source_kind" in columns:
            return
        db.execute("PRAGMA foreign_keys = OFF")
        try:
            db.executescript("""
            BEGIN IMMEDIATE;
            ALTER TABLE imagination_lore_revisions RENAME TO imagination_lore_revisions_legacy;
            ALTER TABLE imagination_lore RENAME TO imagination_lore_legacy;
            CREATE TABLE imagination_lore (
              entity_id TEXT PRIMARY KEY, title TEXT NOT NULL, markdown TEXT NOT NULL,
              version INTEGER NOT NULL, created_turn_id TEXT REFERENCES turns(id),
              updated_turn_id TEXT REFERENCES turns(id), created_source_kind TEXT NOT NULL,
              created_source_id TEXT NOT NULL, updated_source_kind TEXT NOT NULL,
              updated_source_id TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL
            );
            CREATE TABLE imagination_lore_revisions (
              id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES imagination_lore(entity_id),
              version INTEGER NOT NULL, operation TEXT NOT NULL, markdown TEXT NOT NULL,
              turn_id TEXT REFERENCES turns(id), source_kind TEXT NOT NULL, source_id TEXT NOT NULL,
              created_at REAL NOT NULL, UNIQUE(entity_id, version),
              UNIQUE(entity_id, source_kind, source_id)
            );
            INSERT INTO imagination_lore
              SELECT entity_id,title,markdown,version,created_turn_id,updated_turn_id,
                     'turn',created_turn_id,'turn',updated_turn_id,created_at,updated_at
              FROM imagination_lore_legacy;
            INSERT INTO imagination_lore_revisions
              SELECT id,entity_id,version,operation,markdown,turn_id,'turn',turn_id,created_at
              FROM imagination_lore_revisions_legacy;
            DROP TABLE imagination_lore_revisions_legacy;
            DROP TABLE imagination_lore_legacy;
            COMMIT;
            """)
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.execute("PRAGMA foreign_keys = ON")

    @contextmanager
    def transaction(self, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        with self._lock:
            db = self.connect()
            try:
                db.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    def _init(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS conversations (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at REAL NOT NULL,
          updated_at REAL NOT NULL, archived_at REAL
        );
        CREATE TABLE IF NOT EXISTS turns (
          id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
          ordinal INTEGER NOT NULL, status TEXT NOT NULL, outcome TEXT,
          context_state_sequence INTEGER NOT NULL, created_at REAL NOT NULL,
          completed_at REAL, error_code TEXT, input_tokens INTEGER,
          reasoning_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER,
          token_count_source TEXT, context_limit INTEGER,
          UNIQUE(conversation_id, ordinal)
        );
        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY, turn_id TEXT NOT NULL REFERENCES turns(id),
          conversation_id TEXT NOT NULL REFERENCES conversations(id), role TEXT NOT NULL,
          raw_content TEXT NOT NULL, display_content TEXT NOT NULL,
          reasoning_content TEXT, reasoning_kind TEXT, status TEXT NOT NULL,
          created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS turn_contexts (
          turn_id TEXT PRIMARY KEY REFERENCES turns(id), instructions_text TEXT NOT NULL,
          knowledge_text TEXT NOT NULL, conversation_json TEXT NOT NULL,
          state_sequence INTEGER NOT NULL, model_id TEXT NOT NULL, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS turn_braid_contexts (
          turn_id TEXT PRIMARY KEY REFERENCES turns(id), retrieved_memory_json TEXT NOT NULL,
          affect_json TEXT NOT NULL, active_context_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS receipts (
          id TEXT PRIMARY KEY, turn_id TEXT UNIQUE NOT NULL REFERENCES turns(id),
          decision TEXT NOT NULL, outcome TEXT NOT NULL, claim_json TEXT,
          rationale TEXT NOT NULL, decision_basis_json TEXT NOT NULL,
          result_json TEXT, boundary_hash TEXT NOT NULL, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS proposals (
          id TEXT PRIMARY KEY, turn_id TEXT UNIQUE NOT NULL REFERENCES turns(id),
          raw_line TEXT NOT NULL, what_path TEXT, verb TEXT, raw_args TEXT,
          normalized_args_json TEXT, parse_status TEXT NOT NULL, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gate_decisions (
          id TEXT PRIMARY KEY, turn_id TEXT UNIQUE NOT NULL REFERENCES turns(id),
          proposal_id TEXT REFERENCES proposals(id), admission TEXT NOT NULL,
          execution TEXT NOT NULL, persistence TEXT NOT NULL,
          terminal_stage TEXT NOT NULL, checks_json TEXT NOT NULL, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mutations (
          id TEXT PRIMARY KEY, turn_id TEXT UNIQUE NOT NULL REFERENCES turns(id),
          state_sequence_before INTEGER NOT NULL, state_sequence_after INTEGER NOT NULL,
          verb TEXT NOT NULL, what_path TEXT NOT NULL, args_json TEXT NOT NULL,
          result_json TEXT, patch_json TEXT NOT NULL, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS canonical_state (
          singleton INTEGER PRIMARY KEY CHECK(singleton = 1), sequence INTEGER NOT NULL,
          world_json TEXT NOT NULL, self_json TEXT NOT NULL,
          imagination_world_json TEXT NOT NULL DEFAULT '{"schema_version": 2, "sources": {}, "nodes": {}, "edges": [], "constraints": []}',
          updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS seed_imports (
          seed_id TEXT NOT NULL, seed_version INTEGER NOT NULL, seed_hash TEXT NOT NULL,
          source_path TEXT NOT NULL, state_sequence INTEGER NOT NULL, imported_at REAL NOT NULL,
          PRIMARY KEY(seed_id, seed_hash)
        );
        CREATE TABLE IF NOT EXISTS memory_entries (
          id TEXT PRIMARY KEY, scope_type TEXT NOT NULL, scope_id TEXT,
          channel TEXT NOT NULL CHECK(channel IN ('experience','cognitive_semantic','emotional_semantic')),
          content TEXT NOT NULL, origin TEXT NOT NULL DEFAULT 'experience',
          source_event_id TEXT, derived_from_json TEXT NOT NULL DEFAULT '[]',
          affect_before_json TEXT, affect_after_json TEXT, affect_delta_json TEXT,
          visibility TEXT NOT NULL DEFAULT 'standard', created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS affect_state (
          dimension TEXT PRIMARY KEY, current_value REAL NOT NULL, baseline REAL NOT NULL,
          homeostasis_rate REAL NOT NULL, max_delta REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS affect_history (
          id TEXT PRIMARY KEY, source_event_id TEXT NOT NULL UNIQUE, transition_kind TEXT NOT NULL,
          before_json TEXT NOT NULL, delta_json TEXT NOT NULL, after_json TEXT NOT NULL,
          created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS active_context (
          singleton INTEGER PRIMARY KEY CHECK(singleton=1), world_scope TEXT,
          task_scope TEXT, skill_scopes_json TEXT NOT NULL,
          role_scopes_json TEXT NOT NULL DEFAULT '[]', updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS domain_versions (
          domain TEXT PRIMARY KEY, version INTEGER NOT NULL, updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS self_claims (
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL,
          predicate TEXT NOT NULL, value TEXT NOT NULL, status TEXT NOT NULL,
          source TEXT NOT NULL, created_at REAL NOT NULL, self_version INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS capabilities (
          id TEXT PRIMARY KEY, source TEXT NOT NULL, effect_class TEXT NOT NULL,
          description TEXT NOT NULL, schema_json TEXT NOT NULL, scope_json TEXT NOT NULL,
          limits_json TEXT NOT NULL, available INTEGER NOT NULL, boundary_version TEXT NOT NULL,
          created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tool_receipts (
          id TEXT PRIMARY KEY, tool_id TEXT NOT NULL, source TEXT NOT NULL,
          effect_class TEXT NOT NULL, raw_args_json TEXT NOT NULL, normalized_args_json TEXT,
          context_json TEXT NOT NULL, capability_version INTEGER NOT NULL,
          decision TEXT NOT NULL, checks_json TEXT NOT NULL, execution_status TEXT NOT NULL,
          result_json TEXT, error TEXT, created_at REAL NOT NULL, completed_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS turn_system_contexts (
          turn_id TEXT PRIMARY KEY REFERENCES turns(id), projection_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS turn_context_manifests (
          turn_id TEXT PRIMARY KEY REFERENCES turns(id), manifest_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS turn_expression_receipts (
          turn_id TEXT PRIMARY KEY REFERENCES turns(id), profile_json TEXT NOT NULL,
          grounded_visible TEXT NOT NULL, expressed_content TEXT NOT NULL,
          fidelity_json TEXT NOT NULL, fallback INTEGER NOT NULL, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prompt_projections (
          id TEXT PRIMARY KEY, turn_id TEXT UNIQUE REFERENCES turns(id),
          subject_id TEXT NOT NULL, state_sequence INTEGER NOT NULL,
          domain_versions_json TEXT NOT NULL, request_json TEXT NOT NULL,
          strategy_json TEXT NOT NULL, selected_nodes_json TEXT NOT NULL,
          selected_edges_json TEXT NOT NULL, expansion_handles_json TEXT NOT NULL,
          excluded_nodes_json TEXT NOT NULL, rendered_context TEXT NOT NULL,
          estimated_tokens INTEGER NOT NULL, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS imagination_runs (
          id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
          seed TEXT NOT NULL, max_steps INTEGER NOT NULL, completed_steps INTEGER NOT NULL,
          status TEXT NOT NULL, active_turn_id TEXT REFERENCES turns(id),
          created_at REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS imagination_turns (
          run_id TEXT NOT NULL REFERENCES imagination_runs(id),
          turn_id TEXT PRIMARY KEY REFERENCES turns(id), kind TEXT NOT NULL,
          step_number INTEGER, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS imagination_lore (
          entity_id TEXT PRIMARY KEY, title TEXT NOT NULL, markdown TEXT NOT NULL,
          version INTEGER NOT NULL, created_turn_id TEXT REFERENCES turns(id),
          updated_turn_id TEXT REFERENCES turns(id), created_source_kind TEXT NOT NULL,
          created_source_id TEXT NOT NULL, updated_source_kind TEXT NOT NULL,
          updated_source_id TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS imagination_lore_revisions (
          id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES imagination_lore(entity_id),
          version INTEGER NOT NULL, operation TEXT NOT NULL, markdown TEXT NOT NULL,
          turn_id TEXT REFERENCES turns(id), source_kind TEXT NOT NULL, source_id TEXT NOT NULL,
          created_at REAL NOT NULL, UNIQUE(entity_id, version),
          UNIQUE(entity_id, source_kind, source_id)
        );
        CREATE TABLE IF NOT EXISTS imagination_blueprints (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, artifact_type TEXT NOT NULL,
          status TEXT NOT NULL, pack_id TEXT NOT NULL, pack_version INTEGER NOT NULL,
          lens_id TEXT, initiating_pressure_id TEXT, revision INTEGER NOT NULL,
          snapshot_json TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS imagination_blueprint_revisions (
          id TEXT PRIMARY KEY, blueprint_id TEXT NOT NULL REFERENCES imagination_blueprints(id),
          revision INTEGER NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL,
          snapshot_json TEXT NOT NULL, created_at REAL NOT NULL,
          UNIQUE(blueprint_id, revision)
        );
        CREATE TABLE IF NOT EXISTS imagination_admissions (
          id TEXT PRIMARY KEY, blueprint_id TEXT NOT NULL REFERENCES imagination_blueprints(id),
          blueprint_revision INTEGER NOT NULL, candidate_id TEXT NOT NULL,
          candidate_hash TEXT NOT NULL, state_sequence_before INTEGER NOT NULL,
          state_sequence_after INTEGER NOT NULL, entity_mapping_json TEXT NOT NULL,
          genealogy_json TEXT NOT NULL, receipt_json TEXT NOT NULL, created_at REAL NOT NULL,
          UNIQUE(blueprint_id), UNIQUE(candidate_hash)
        );
        CREATE TABLE IF NOT EXISTS imagination_world_pressures (
          id TEXT PRIMARY KEY, subject_entity_id TEXT NOT NULL, kind TEXT NOT NULL,
          status TEXT NOT NULL, reason TEXT NOT NULL, hint_json TEXT,
          possible_resolutions_json TEXT NOT NULL,
          source_admission_id TEXT NOT NULL REFERENCES imagination_admissions(id),
          source_primitive_id TEXT, exploration_blueprint_id TEXT REFERENCES imagination_blueprints(id),
          created_at REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_world_pressures_status ON imagination_world_pressures(status, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_turns_conversation ON turns(conversation_id, ordinal);
        CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_blueprints_updated ON imagination_blueprints(updated_at DESC);
        """
        with self.connect() as db:
            db.executescript(schema)
            self._migrate_lore_provenance(db)
            columns = {row[1] for row in db.execute("PRAGMA table_info(canonical_state)")}
            if "imagination_world_json" not in columns:
                db.execute(
                    "ALTER TABLE canonical_state ADD COLUMN imagination_world_json TEXT NOT NULL "
                    "DEFAULT '{\"schema_version\": 2, \"sources\": {}, \"nodes\": {}, \"edges\": [], \"constraints\": []}'"
                )
            context_columns = {row[1] for row in db.execute("PRAGMA table_info(active_context)")}
            if "role_scopes_json" not in context_columns:
                db.execute("ALTER TABLE active_context ADD COLUMN role_scopes_json TEXT NOT NULL DEFAULT '[]'")
            now = time.time()
            world = empty_world()
            self_state = {"name": "halcyon", "memory": {}}
            db.execute(
                "INSERT OR IGNORE INTO canonical_state (singleton, sequence, world_json, self_json, imagination_world_json, updated_at) "
                "VALUES (1, 0, ?, ?, ?, ?)",
                (json.dumps(world), json.dumps(self_state), json.dumps(empty_world()), now),
            )
            for dimension in ('joy','sadness','fear','anger','trust','disgust','surprise','anticipation'):
                db.execute("INSERT OR IGNORE INTO affect_state VALUES (?,50.0,50.0,0.015,10.0,?)", (dimension, now))
            db.execute(
                "INSERT OR IGNORE INTO active_context (singleton, world_scope, task_scope, skill_scopes_json, role_scopes_json, updated_at) "
                "VALUES (1,'world:iris',NULL,'[]','[]',?)", (now,))
            db.execute("UPDATE active_context SET world_scope='world:halcyon',updated_at=? WHERE world_scope='world:iris'", (now,))
            for domain in ("self", "memory", "affect", "context", "capabilities", "governance"):
                db.execute("INSERT OR IGNORE INTO domain_versions VALUES (?,0,?)", (domain, now))
            self._install_identity(db, now)
            defaults = (
                ("system.inspect", "builtin", "observe", "Inspect the composed Halcyon System Identity projection", "{}"),
                ("memory.search", "builtin", "observe", "Search currently reachable scoped Memory", '{"query":{"type":"string","required":true}}'),
                ("affect.inspect", "builtin", "observe", "Inspect effective Affect and recent trajectory", "{}"),
                ("graph.inspect", "builtin", "observe", "Inspect one authorized node in the Self-centered projection graph", '{"node_id":{"type":"string","required":true}}'),
                ("graph.neighbors", "builtin", "observe", "Traverse authorized projection-graph relationships from one node", '{"node_id":{"type":"string","required":true},"edges":{"type":"array"},"depth":{"type":"integer"},"limit":{"type":"integer"}}'),
                ("graph.search", "builtin", "observe", "Search the authorized Self-centered projection graph", '{"query":{"type":"string","required":true},"domains":{"type":"array"},"limit":{"type":"integer"}}'),
            )
            for tool_id, source, effect, description, schema_json in defaults:
                db.execute("INSERT OR IGNORE INTO capabilities VALUES (?,?,?,?,?,'{}','{}',1,'capability-v1',?)",
                           (tool_id, source, effect, description, schema_json, now))
            db.execute("UPDATE capabilities SET description=? WHERE id='system.inspect'",
                       ("Inspect the composed Halcyon System Identity projection",))
            db.execute("UPDATE domain_versions SET version=MAX(version,1),updated_at=? WHERE domain='capabilities'", (now,))
            db.commit()
        self.recover_interrupted()

    @staticmethod
    def _lore_targets(result: dict | None) -> list[str]:
        """Entity ids touched by one admitted Imagination mutation."""
        result = result or {}
        targets: list[str] = []
        if isinstance(result.get("created"), str):
            targets.append(result["created"])
        for key in ("related", "occurred"):
            edge = result.get(key)
            if isinstance(edge, dict):
                targets.extend(value for value in (edge.get("source"), edge.get("target")) if isinstance(value, str))
        constrained = result.get("constrained")
        if isinstance(constrained, dict) and isinstance(constrained.get("target"), str):
            targets.append(constrained["target"])
        return list(dict.fromkeys(targets))

    @staticmethod
    def _append_imagination_lore(db: sqlite3.Connection, entity_id: str, title: str,
                                 prose: str, source_kind: str, source_id: str, now: float,
                                 turn_id: str | None = None, complete_markdown: bool = False) -> None:
        prose = prose.strip()
        if not prose or db.execute(
            "SELECT 1 FROM imagination_lore_revisions WHERE entity_id=? AND source_kind=? AND source_id=?",
            (entity_id, source_kind, source_id),
        ).fetchone():
            return
        current = db.execute("SELECT * FROM imagination_lore WHERE entity_id=?", (entity_id,)).fetchone()
        if current:
            version = current["version"] + 1
            markdown = prose.rstrip() + "\n" if complete_markdown else current["markdown"].rstrip() + f"\n\n## Development {version}\n\n{prose}\n"
            operation = "append"
            db.execute(
                "UPDATE imagination_lore SET title=?,markdown=?,version=?,updated_turn_id=?,"
                "updated_source_kind=?,updated_source_id=?,updated_at=? WHERE entity_id=?",
                (title, markdown, version, turn_id, source_kind, source_id, now, entity_id),
            )
        else:
            version, operation = 1, "create"
            markdown = prose.rstrip() + "\n" if complete_markdown else f"# {title}\n\n{prose}\n"
            db.execute(
                "INSERT INTO imagination_lore (entity_id,title,markdown,version,created_turn_id,updated_turn_id,"
                "created_source_kind,created_source_id,updated_source_kind,updated_source_id,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (entity_id, title, markdown, version, turn_id, turn_id, source_kind, source_id,
                 source_kind, source_id, now, now),
            )
        db.execute(
            "INSERT INTO imagination_lore_revisions "
            "(id,entity_id,version,operation,markdown,turn_id,source_kind,source_id,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (_id("lore_rev"), entity_id, version, operation, markdown, turn_id, source_kind, source_id, now),
        )

    @staticmethod
    def _install_identity(db: sqlite3.Connection, now: float) -> None:
        """Idempotently migrate the active Self to the reviewed Halcyon manifest.

        Runs on every Store construction, so it must not clobber an identity pack
        (iris/identity_packs.py) a caller switched in — otherwise every restart
        would silently revert the active Self back to Halcyon. Skip entirely if
        some other subject already holds the active claims; only migrate when
        Halcyon is the active Self or no Self has been installed yet.
        """
        other_active = db.execute(
            "SELECT 1 FROM self_claims WHERE status='active' AND subject!='Halcyon' LIMIT 1"
        ).fetchone()
        if other_active:
            return
        manifest_path = Path(__file__).resolve().parent.parent / "seeds" / "halcyon_identity.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        version = int(manifest["version"])
        row = db.execute("SELECT self_json FROM canonical_state WHERE singleton=1").fetchone()
        if row:
            self_state = json.loads(row["self_json"])
            if self_state.get("name") != "halcyon":
                self_state["name"] = "halcyon"
                db.execute("UPDATE canonical_state SET self_json=?,updated_at=? WHERE singleton=1",
                           (json.dumps(self_state, ensure_ascii=False), now))
        db.execute("UPDATE self_claims SET status='superseded' WHERE id='self:identity:name' AND value!='Halcyon'")
        for claim in manifest["claims"]:
            db.execute(
                "INSERT OR REPLACE INTO self_claims VALUES (?,?,?,?,?,'active',?,?,?)",
                (claim["id"], claim["kind"], claim["subject"], claim["predicate"],
                 claim["value"], claim["source"], now, version),
            )
        db.execute("UPDATE domain_versions SET version=MAX(version,?),updated_at=? WHERE domain='self'",
                   (version, now))

    def recover_interrupted(self) -> None:
        now = time.time()
        with self.transaction(immediate=True) as db:
            db.execute(
                "UPDATE turns SET status='interrupted', outcome='none', completed_at=?, "
                "error_code='server_interrupted' WHERE status IN ('generating','finalizing')",
                (now,),
            )
            db.execute("UPDATE imagination_runs SET status='paused',active_turn_id=NULL,updated_at=? WHERE status='running'", (now,))

    def create_imagination_run(self, seed: str, max_steps: int, running: bool = True) -> dict:
        now, run_id, conversation_id = time.time(), _id("imagine"), _id("conv")
        title = f"Imagination · {' '.join(seed.split())[:42]}"
        status = "running" if running else "paused"
        with self.transaction(immediate=True) as db:
            db.execute("INSERT INTO conversations VALUES (?,?,?,?,NULL)", (conversation_id, title, now, now))
            db.execute("INSERT INTO imagination_runs VALUES (?,?,?,?,0,?,NULL,?,?)",
                       (run_id, conversation_id, seed, max_steps, status, now, now))
        return self.imagination_run(run_id)

    def imagination_run(self, run_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM imagination_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["conversation"] = self.conversation(result["conversation_id"])
        with self.connect() as db:
            turns = db.execute("SELECT turn_id,kind,step_number FROM imagination_turns WHERE run_id=?", (run_id,)).fetchall()
        result["turn_kinds"] = {item["turn_id"]: {"kind": item["kind"], "step": item["step_number"]} for item in turns}
        return result

    def imagination_runs(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM imagination_runs ORDER BY created_at DESC LIMIT 50").fetchall()
        return [dict(row) for row in rows]

    def set_imagination_status(self, run_id: str, status: str) -> dict | None:
        if status not in {"running", "paused", "cancelled", "complete", "failed"}:
            raise ValueError("invalid imagination status")
        with self.transaction(immediate=True) as db:
            db.execute("UPDATE imagination_runs SET status=?,updated_at=? WHERE id=?", (status, time.time(), run_id))
        return self.imagination_run(run_id)

    def imagination_step_started(self, run_id: str, turn_id: str) -> None:
        with self.transaction(immediate=True) as db:
            db.execute("UPDATE imagination_runs SET active_turn_id=?,updated_at=? WHERE id=?",
                       (turn_id, time.time(), run_id))

    def link_imagination_turn(self, run_id: str, turn_id: str, kind: str,
                              step_number: int | None = None) -> None:
        if kind not in {"chat", "autonomous"}:
            raise ValueError("invalid imagination turn kind")
        with self.transaction(immediate=True) as db:
            db.execute("INSERT INTO imagination_turns VALUES (?,?,?,?,?)",
                       (run_id, turn_id, kind, step_number, time.time()))

    def start_imagination_batch(self, run_id: str, steps: int) -> dict | None:
        if not 1 <= steps <= 20:
            raise ValueError("imagination batch must contain 1 to 20 turns")
        with self.transaction(immediate=True) as db:
            row = db.execute("SELECT completed_steps FROM imagination_runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                return None
            db.execute("UPDATE imagination_runs SET max_steps=?,status='running',updated_at=? WHERE id=?",
                       (row["completed_steps"] + steps, time.time(), run_id))
        return self.imagination_run(run_id)

    def imagination_step_finished(self, run_id: str, failed: bool = False) -> dict:
        with self.transaction(immediate=True) as db:
            row = db.execute("SELECT * FROM imagination_runs WHERE id=?", (run_id,)).fetchone()
            completed = row["completed_steps"] + (0 if failed else 1)
            if failed:
                status = "failed"
            elif row["status"] in {"paused", "cancelled"}:
                status = row["status"]
            elif completed >= row["max_steps"]:
                status = "complete"
            else:
                status = "running"
            db.execute("UPDATE imagination_runs SET completed_steps=?,status=?,active_turn_id=NULL,updated_at=? WHERE id=?",
                       (completed, status, time.time(), run_id))
        return self.imagination_run(run_id)

    def state(self, db: sqlite3.Connection | None = None) -> tuple[int, dict]:
        owns = db is None
        db = db or self.connect()
        try:
            row = db.execute("SELECT * FROM canonical_state WHERE singleton=1").fetchone()
            return row["sequence"], {
                "world": normalize_world(json.loads(row["world_json"])),
                "self": json.loads(row["self_json"]),
                "imagination_world": normalize_world(json.loads(row["imagination_world_json"])),
            }
        finally:
            if owns:
                db.close()

    def conversations(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT c.*, COUNT(t.id) turn_count FROM conversations c "
                "LEFT JOIN turns t ON t.conversation_id=c.id "
                "WHERE c.archived_at IS NULL AND NOT EXISTS "
                "(SELECT 1 FROM imagination_runs i WHERE i.conversation_id=c.id) "
                "GROUP BY c.id ORDER BY c.updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def conversation(self, conversation_id: str) -> dict | None:
        with self.connect() as db:
            conv = db.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
            if not conv:
                return None
            messages = db.execute(
                "SELECT m.*, t.status turn_status, t.outcome, t.input_tokens, "
                "t.reasoning_tokens, t.output_tokens, t.total_tokens, t.token_count_source "
                "FROM messages m JOIN turns t ON t.id=m.turn_id "
                "WHERE m.conversation_id=? ORDER BY m.created_at, m.role DESC",
                (conversation_id,),
            ).fetchall()
            active = db.execute(
                "SELECT * FROM turns WHERE conversation_id=? AND status IN ('generating','finalizing')",
                (conversation_id,),
            ).fetchone()
            return {**dict(conv), "messages": [dict(r) for r in messages],
                    "active_turn": dict(active) if active else None}

    def begin_turn(self, conversation_id: str | None, content: str, context: dict) -> dict:
        now = time.time()
        conversation_id = conversation_id or _id("conv")
        turn_id, message_id = _id("turn"), _id("msg")
        title = " ".join(content.strip().split())[:56] or "New conversation"
        with self.transaction(immediate=True) as db:
            existing = db.execute("SELECT id FROM conversations WHERE id=?", (conversation_id,)).fetchone()
            if not existing:
                db.execute("INSERT INTO conversations VALUES (?, ?, ?, ?, NULL)",
                           (conversation_id, title, now, now))
            active = db.execute(
                "SELECT id FROM turns WHERE conversation_id=? AND status IN ('generating','finalizing')",
                (conversation_id,),
            ).fetchone()
            if active:
                raise ConversationBusy(active["id"])
            ordinal = db.execute(
                "SELECT COALESCE(MAX(ordinal),0)+1 n FROM turns WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()["n"]
            db.execute(
                "INSERT INTO turns (id,conversation_id,ordinal,status,outcome,context_state_sequence,created_at,context_limit) "
                "VALUES (?,?,?,'generating',NULL,?,?,?)",
                (turn_id, conversation_id, ordinal, context["state_sequence"], now, context["context_limit"]),
            )
            db.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?,?,NULL,NULL,'final',?)",
                (message_id, turn_id, conversation_id, "user", content, content, now),
            )
            db.execute(
                "INSERT INTO turn_contexts VALUES (?,?,?,?,?,?,?)",
                (turn_id, context["instructions"], context["knowledge"],
                 json.dumps(context["conversation"]), context["state_sequence"],
                 context["model_id"], now),
            )
            db.execute("INSERT INTO turn_braid_contexts VALUES (?,?,?,?)",
                       (turn_id, json.dumps(context.get("retrieved_memory", [])),
                        json.dumps(context.get("affect", {})), json.dumps(context.get("active_context", {}))))
            db.execute("INSERT INTO turn_system_contexts VALUES (?,?)",
                       (turn_id, json.dumps(context.get("system_projection", {}))))
            db.execute("INSERT INTO turn_context_manifests VALUES (?,?)",
                       (turn_id, json.dumps(context.get("context_manifest", {}))))
            projection = context.get("prompt_projection")
            if projection:
                db.execute(
                    "INSERT INTO prompt_projections VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (projection["id"], turn_id, projection["subject_id"], projection["state_sequence"],
                     json.dumps(projection["domain_versions"]), json.dumps(projection["request"]),
                     json.dumps(projection["strategy"]), json.dumps(projection["selected_nodes"]),
                     json.dumps(projection["selected_edges"]), json.dumps(projection["expansion_handles"]),
                     json.dumps(projection["excluded"]), projection["rendered_context"],
                     projection["estimated_tokens"], projection["created_at"]),
                )
            db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))
        return {"id": turn_id, "conversation_id": conversation_id, "ordinal": ordinal,
                "status": "generating", "created_at": now, "user_message_id": message_id}

    def append_context_message(self, conversation_id: str | None, raw: str, display: str,
                               title_hint: str = "New conversation") -> dict:
        """Append user-provided context without starting a model generation."""
        now = time.time()
        conversation_id = conversation_id or _id("conv")
        turn_id, message_id = _id("turn"), _id("msg")
        title = " ".join(title_hint.strip().split())[:56] or "New conversation"
        with self.transaction(immediate=True) as db:
            sequence, _ = self.state(db)
            existing = db.execute("SELECT id FROM conversations WHERE id=?", (conversation_id,)).fetchone()
            if not existing:
                db.execute("INSERT INTO conversations VALUES (?, ?, ?, ?, NULL)",
                           (conversation_id, title, now, now))
            active = db.execute(
                "SELECT id FROM turns WHERE conversation_id=? AND status IN ('generating','finalizing')",
                (conversation_id,),
            ).fetchone()
            if active:
                raise ConversationBusy(active["id"])
            ordinal = db.execute(
                "SELECT COALESCE(MAX(ordinal),0)+1 n FROM turns WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()["n"]
            db.execute(
                "INSERT INTO turns (id,conversation_id,ordinal,status,outcome,context_state_sequence,created_at,completed_at) "
                "VALUES (?,?,?,'complete','none',?,?,?)",
                (turn_id, conversation_id, ordinal, sequence, now, now),
            )
            db.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?,?,NULL,NULL,'final',?)",
                (message_id, turn_id, conversation_id, "user", raw, display, now),
            )
            db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))
        return {"id": message_id, "turn_id": turn_id, "conversation_id": conversation_id,
                "role": "user", "raw_content": raw, "display_content": display,
                "turn_status": "complete", "outcome": "none", "created_at": now}

    def mark_finalizing(self, turn_id: str) -> None:
        with self.transaction(immediate=True) as db:
            db.execute("UPDATE turns SET status='finalizing' WHERE id=? AND status='generating'", (turn_id,))

    def fail_turn(self, turn_id: str, code: str, cancelled: bool = False) -> dict:
        now = time.time()
        status = "cancelled" if cancelled else "failed"
        with self.transaction(immediate=True) as db:
            db.execute(
                "UPDATE turns SET status=?, outcome='none', error_code=?, completed_at=? WHERE id=?",
                (status, code, now, turn_id),
            )
            row = db.execute("SELECT * FROM turns WHERE id=?", (turn_id,)).fetchone()
        return dict(row)

    def finalize(self, turn_id: str, raw: str, display: str, reasoning: str | None,
                 reasoning_kind: str | None, receipt: dict, new_state: dict,
                 expected_sequence: int, boundary_hash: str, proposal: dict | None,
                 usage: dict, affect_values: dict[str, float] | None = None,
                 expression_receipt: dict | None = None) -> dict:
        now = time.time()
        with self.transaction(immediate=True) as db:
            turn = db.execute("SELECT * FROM turns WHERE id=?", (turn_id,)).fetchone()
            current_sequence, old_state = self.state(db)
            if current_sequence != expected_sequence:
                raise StateConflict(current_sequence)
            outcome = receipt_outcome(receipt)
            state_changed = new_state != old_state and receipt["decision"] == "ACCEPT"
            affect_transition = self._apply_affect_values(db, turn_id, affect_values, now) if affect_values else None
            changed = state_changed or affect_transition is not None
            next_sequence = current_sequence + 1 if changed else current_sequence
            if changed:
                db.execute(
                    "UPDATE canonical_state SET sequence=?, world_json=?, self_json=?, imagination_world_json=?, updated_at=? WHERE singleton=1",
                    (next_sequence, json.dumps(new_state["world"]), json.dumps(new_state["self"]),
                     json.dumps(new_state["imagination_world"]), now),
                )
            message_id = _id("msg")
            db.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?, 'final', ?)",
                (message_id, turn_id, turn["conversation_id"], "assistant", raw, display,
                 reasoning, reasoning_kind, now),
            )
            proposal_id = None
            if proposal:
                proposal_id = _id("prop")
                db.execute(
                    "INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?)",
                    (proposal_id, turn_id, proposal["raw_line"], proposal.get("what_path"),
                     proposal.get("verb"), proposal.get("raw_args"),
                     json.dumps(proposal.get("normalized_args")) if proposal.get("normalized_args") else None,
                     proposal["parse_status"], now),
                )
            receipt_id = receipt["id"]
            db.execute(
                "INSERT INTO receipts VALUES (?,?,?,?,?,?,?,?,?,?)",
                (receipt_id, turn_id, receipt["decision"], outcome,
                 json.dumps(receipt["claim"]) if receipt.get("claim") else None,
                 receipt["rationale"], json.dumps(receipt["decision_basis"]),
                 json.dumps(receipt["result"]) if receipt.get("result") is not None else None,
                 boundary_hash, now),
            )
            admission, execution, persistence, terminal = decision_dimensions(receipt, changed)
            decision_id = _id("gate")
            db.execute(
                "INSERT INTO gate_decisions VALUES (?,?,?,?,?,?,?,?,?)",
                (decision_id, turn_id, proposal_id, admission, execution, persistence,
                 terminal, json.dumps(receipt["decision_basis"]), now),
            )
            if state_changed:
                claim = receipt["claim"]
                db.execute(
                    "INSERT INTO mutations VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (_id("mut"), turn_id, current_sequence, next_sequence, claim["verb"],
                     claim["what"], json.dumps(claim["args"]), json.dumps(receipt.get("result")),
                     json.dumps({"before": old_state, "after": new_state}), now),
                )
                if claim["what"].startswith("world/"):
                    world = normalize_world(new_state["imagination_world"])
                    for entity_id in self._lore_targets(receipt.get("result")):
                        node = world["nodes"].get(entity_id, {})
                        title = node.get("label") or entity_id.removeprefix("entity:").replace("-", " ").title()
                        self._append_imagination_lore(db, entity_id, title, display,
                                                      "turn", turn_id, now, turn_id=turn_id)
            db.execute(
                "UPDATE turns SET status='complete', outcome=?, completed_at=?, input_tokens=?, "
                "reasoning_tokens=?, output_tokens=?, total_tokens=?, token_count_source=? WHERE id=?",
                (outcome, now, usage.get("input_tokens"), usage.get("reasoning_tokens"),
                 usage.get("output_tokens"), usage.get("total_tokens"), usage.get("source"), turn_id),
            )
            if expression_receipt:
                db.execute(
                    "INSERT INTO turn_expression_receipts VALUES (?,?,?,?,?,?,?)",
                    (turn_id, json.dumps(expression_receipt.get("profile", {})),
                     expression_receipt.get("grounded_visible", ""), display,
                     json.dumps(expression_receipt.get("fidelity", {})),
                     int(bool(expression_receipt.get("fallback"))), now),
                )
            db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, turn["conversation_id"]))
        if changed:
            self.write_projections(next_sequence, new_state)
        return {"turn_id": turn_id, "message_id": message_id, "status": "complete",
                "outcome": outcome, "state_sequence": next_sequence, "receipt_id": receipt_id,
                "proposal_id": proposal_id, "gate_decision_id": decision_id,
                "display_content": display, "reasoning_content": reasoning,
                "reasoning_kind": reasoning_kind, "usage": usage,
                "affect_transition": affect_transition}

    def _apply_affect_values(self, db: sqlite3.Connection, source_event_id: str,
                             values: dict[str, float], now: float) -> dict:
        if db.execute("SELECT 1 FROM affect_history WHERE source_event_id=?", (source_event_id,)).fetchone():
            raise ValueError("affect event already applied")
        rows = db.execute("SELECT * FROM affect_state ORDER BY rowid").fetchall()
        known = {row["dimension"]: row for row in rows}
        if set(values) != set(known):
            raise ValueError("affect proposal must contain all configured dimensions")
        before, after, delta = {}, {}, {}
        for dimension, row in known.items():
            hours = max(0.0, (now - row["updated_at"]) / 3600.0)
            current = row["current_value"] + (row["baseline"] - row["current_value"]) * min(1.0, row["homeostasis_rate"] * hours)
            value = float(values[dimension])
            change = value - current
            if not (1.0 <= value <= 100.0) or abs(change) > row["max_delta"]:
                raise ValueError(f"invalid affect transition for {dimension}")
            before[dimension], after[dimension], delta[dimension] = round(current, 2), round(value, 2), round(change, 2)
            db.execute("UPDATE affect_state SET current_value=?,updated_at=? WHERE dimension=?", (value, now, dimension))
        history_id = _id("aff")
        db.execute("INSERT INTO affect_history VALUES (?,?,?,?,?,?,?)",
                   (history_id, source_event_id, "model", json.dumps(before), json.dumps(delta), json.dumps(after), now))
        self._bump_domain(db, "affect")
        return {"id": history_id, "source_event_id": source_event_id, "before": before, "delta": delta, "after": after, "created_at": now}

    def write_projections(self, sequence: int, state: dict) -> None:
        for name in ("world", "self"):
            target = self.state_dir / f"{name}.json"
            temp = self.state_dir / f".{name}.json.tmp"
            value = dict(state[name])
            value["_state_sequence"] = sequence
            temp.write_text(json.dumps(value, indent=1), encoding="utf-8")
            temp.replace(target)

    def context_messages(self, conversation_id: str, limit: int = 20) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT role, raw_content, display_content FROM messages WHERE conversation_id=? AND status='final' "
                "ORDER BY created_at DESC LIMIT ?", (conversation_id, limit),
            ).fetchall()
            return [{"role": r["role"], "content": r["display_content"] if r["role"] == "assistant" else r["raw_content"]}
                    for r in reversed(rows)]

    def turn(self, turn_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM turns WHERE id=?", (turn_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            msg = db.execute("SELECT * FROM messages WHERE turn_id=? AND role='assistant'", (turn_id,)).fetchone()
            data["assistant_message"] = dict(msg) if msg else None
            rec = db.execute("SELECT * FROM receipts WHERE turn_id=?", (turn_id,)).fetchone()
            data["receipt"] = dict(rec) if rec else None
            return data

    def turn_context(self, turn_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM turn_contexts WHERE turn_id=?", (turn_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            data["conversation"] = json.loads(data.pop("conversation_json"))
            braid = db.execute("SELECT * FROM turn_braid_contexts WHERE turn_id=?", (turn_id,)).fetchone()
            if braid:
                data["retrieved_memory"] = json.loads(braid["retrieved_memory_json"])
                data["affect"] = json.loads(braid["affect_json"])
                data["active_context"] = json.loads(braid["active_context_json"])
            system = db.execute("SELECT projection_json FROM turn_system_contexts WHERE turn_id=?", (turn_id,)).fetchone()
            data["system_projection"] = json.loads(system["projection_json"]) if system else {}
            manifest = db.execute("SELECT manifest_json FROM turn_context_manifests WHERE turn_id=?", (turn_id,)).fetchone()
            data["context_manifest"] = json.loads(manifest["manifest_json"]) if manifest else {}
            expression = db.execute("SELECT * FROM turn_expression_receipts WHERE turn_id=?", (turn_id,)).fetchone()
            if expression:
                data["expression_receipt"] = {
                    **dict(expression),
                    "profile": json.loads(expression["profile_json"]),
                    "fidelity": json.loads(expression["fidelity_json"]),
                    "fallback": bool(expression["fallback"]),
                }
            projection = db.execute("SELECT id FROM prompt_projections WHERE turn_id=?", (turn_id,)).fetchone()
            data["prompt_projection"] = self.prompt_projection(projection["id"]) if projection else None
            return data

    def prompt_projection(self, projection_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM prompt_projections WHERE id=?", (projection_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        for key in ("domain_versions", "request", "strategy", "selected_nodes",
                    "selected_edges", "expansion_handles", "excluded_nodes"):
            item[key] = json.loads(item.pop(f"{key}_json"))
        return item

    def prompt_projections(self, conversation_id: str | None = None,
                           limit: int = 50) -> list[dict]:
        limit = min(200, max(1, int(limit)))
        query = (
            "SELECT p.id FROM prompt_projections p JOIN turns t ON t.id=p.turn_id "
            + ("WHERE t.conversation_id=? " if conversation_id else "")
            + "ORDER BY p.created_at DESC LIMIT ?"
        )
        params = (conversation_id, limit) if conversation_id else (limit,)
        with self.connect() as db:
            rows = db.execute(query, params).fetchall()
        return [item for row in rows if (item := self.prompt_projection(row["id"]))]

    def governance(self, table: str) -> list[dict]:
        if table not in {"proposals", "gate_decisions", "receipts"}:
            raise ValueError(table)
        with self.connect() as db:
            rows = db.execute(
                f"SELECT x.*, t.conversation_id, t.ordinal FROM {table} x "
                "JOIN turns t ON t.id=x.turn_id ORDER BY x.created_at DESC LIMIT 200"
            ).fetchall()
            return [dict(r) for r in rows]

    def node_provenance(self, node_name: str) -> dict | None:
        """Return the earliest committed mutation that explicitly created a node."""
        with self.connect() as db:
            rows = db.execute(
                "SELECT m.*, t.conversation_id, t.ordinal, r.id receipt_id "
                "FROM mutations m JOIN turns t ON t.id=m.turn_id "
                "LEFT JOIN receipts r ON r.turn_id=m.turn_id ORDER BY m.state_sequence_after"
            ).fetchall()
            for row in rows:
                args = json.loads(row["args_json"])
                if (row["verb"] == "create" and args.get("name") == node_name) or (
                    row["verb"] == "occur" and args.get("event") == node_name
                ):
                    return dict(row)
        return None

    def imagination_lore(self, entity_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM imagination_lore WHERE entity_id=?", (entity_id,)).fetchone()
            if not row:
                return None
            revisions = db.execute(
                "SELECT id,entity_id,version,operation,turn_id,source_kind,source_id,created_at "
                "FROM imagination_lore_revisions WHERE entity_id=? ORDER BY version DESC",
                (entity_id,),
            ).fetchall()
        return {**dict(row), "revisions": [dict(item) for item in revisions]}

    @staticmethod
    def _decode_blueprint(row: sqlite3.Row, revisions: list[sqlite3.Row] | None = None) -> dict:
        item = json.loads(row["snapshot_json"])
        item.update({"id": row["id"], "title": row["title"], "artifact_type": row["artifact_type"],
                     "status": row["status"], "pack_id": row["pack_id"],
                     "pack_version": row["pack_version"], "lens_id": row["lens_id"],
                     "initiating_pressure_id": row["initiating_pressure_id"],
                     "revision": row["revision"], "created_at": row["created_at"],
                     "updated_at": row["updated_at"]})
        if revisions is not None:
            item["revisions"] = [{**dict(revision),
                "snapshot": json.loads(revision["snapshot_json"])} for revision in revisions]
            for revision in item["revisions"]:
                revision.pop("snapshot_json", None)
        return item

    def create_blueprint(self, title: str, artifact_type: str, pack_id: str, pack_version: int,
                         lens_id: str | None, initiating_pressure_id: str | None,
                         content: dict, actor: str = "user", reason: str = "created") -> dict:
        now = time.time()
        blueprint_id = f"blueprint:{uuid.uuid4().hex[:16]}"
        snapshot = {**content, "id": blueprint_id, "title": title, "artifact_type": artifact_type,
                    "status": "draft", "pack_id": pack_id, "pack_version": pack_version,
                    "lens_id": lens_id, "initiating_pressure_id": initiating_pressure_id,
                    "revision": 1, "created_at": now, "updated_at": now}
        encoded = json.dumps(snapshot)
        with self.transaction(immediate=True) as db:
            db.execute("INSERT INTO imagination_blueprints VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (blueprint_id, title, artifact_type, "draft", pack_id, pack_version,
                        lens_id, initiating_pressure_id, 1, encoded, now, now))
            db.execute("INSERT INTO imagination_blueprint_revisions VALUES (?,?,?,?,?,?,?)",
                       (_id("blueprint_rev"), blueprint_id, 1, actor, reason, encoded, now))
        return self.blueprint(blueprint_id)

    def blueprints(self, status: str | None = None) -> list[dict]:
        query = "SELECT * FROM imagination_blueprints"
        params: tuple = ()
        if status:
            query += " WHERE status=?"; params = (status,)
        query += " ORDER BY updated_at DESC"
        with self.connect() as db:
            rows = db.execute(query, params).fetchall()
        return [self._decode_blueprint(row) for row in rows]

    def blueprint(self, blueprint_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM imagination_blueprints WHERE id=?", (blueprint_id,)).fetchone()
            if not row:
                return None
            revisions = db.execute(
                "SELECT * FROM imagination_blueprint_revisions WHERE blueprint_id=? ORDER BY revision DESC",
                (blueprint_id,),
            ).fetchall()
        return self._decode_blueprint(row, revisions)

    def update_blueprint(self, blueprint_id: str, expected_revision: int, patch: dict,
                         actor: str = "user", reason: str = "updated") -> dict:
        immutable = {"id", "pack_id", "pack_version", "created_at", "revision", "revisions"}
        if immutable.intersection(patch):
            raise ValueError("blueprint patch contains immutable fields")
        now = time.time()
        with self.transaction(immediate=True) as db:
            row = db.execute("SELECT * FROM imagination_blueprints WHERE id=?", (blueprint_id,)).fetchone()
            if not row:
                raise KeyError(blueprint_id)
            if row["revision"] != expected_revision:
                raise BlueprintConflict(row["revision"])
            current = self._decode_blueprint(row)
            snapshot = {key: value for key, value in current.items() if key != "revisions"}
            snapshot.update(patch)
            title = str(patch.get("title", row["title"])).strip() or row["title"]
            artifact_type = str(patch.get("artifact_type", row["artifact_type"])).strip() or row["artifact_type"]
            status = patch.get("status", row["status"])
            lens_id = patch.get("lens_id", row["lens_id"])
            initiating_pressure_id = patch.get("initiating_pressure_id", row["initiating_pressure_id"])
            next_revision = expected_revision + 1
            snapshot.update({"id": blueprint_id, "title": title, "artifact_type": artifact_type,
                             "status": status, "pack_id": row["pack_id"],
                             "pack_version": row["pack_version"], "lens_id": lens_id,
                             "initiating_pressure_id": initiating_pressure_id,
                             "revision": next_revision, "created_at": row["created_at"],
                             "updated_at": now})
            encoded = json.dumps(snapshot)
            db.execute(
                "UPDATE imagination_blueprints SET title=?,artifact_type=?,status=?,lens_id=?,"
                "initiating_pressure_id=?,revision=?,snapshot_json=?,updated_at=? WHERE id=?",
                (title, artifact_type, status, lens_id, initiating_pressure_id,
                 next_revision, encoded, now, blueprint_id),
            )
            db.execute("INSERT INTO imagination_blueprint_revisions VALUES (?,?,?,?,?,?,?)",
                       (_id("blueprint_rev"), blueprint_id, next_revision, actor, reason, encoded, now))
        return self.blueprint(blueprint_id)

    def admit_blueprint(self, blueprint_id: str, expected_revision: int,
                        candidate_hash: str) -> dict:
        """Atomically promote one complete candidate graph, its lore, and genealogy."""
        now = time.time()
        admission_id = f"admission:{uuid.uuid4().hex[:16]}"
        committed_state: dict | None = None
        next_sequence = 0
        with self.transaction(immediate=True) as db:
            row = db.execute("SELECT * FROM imagination_blueprints WHERE id=?", (blueprint_id,)).fetchone()
            if not row:
                raise KeyError(blueprint_id)
            if row["revision"] != expected_revision:
                raise BlueprintConflict(row["revision"])
            if row["status"] != "candidate":
                raise ValueError("only a composed candidate can be admitted")
            blueprint = self._decode_blueprint(row)
            candidate = blueprint.get("candidate") or {}
            if candidate.get("content_hash") != candidate_hash:
                raise ValueError("candidate hash does not match the composed revision")
            sequence, state = self.state(db)
            world = normalize_world(state["imagination_world"])
            mapping: dict[str, str] = {}
            canonical_ids: set[str] = set()
            for draft in candidate.get("entities", []):
                canonical_id = f"entity:{slug(draft['label'])}"
                if canonical_id in world["nodes"] or canonical_id in canonical_ids:
                    raise ValueError(f"canonical entity already exists: {canonical_id}")
                mapping[draft["id"]] = canonical_id
                canonical_ids.add(canonical_id)
            for draft in candidate.get("entities", []):
                canonical_id = mapping[draft["id"]]
                world["nodes"][canonical_id] = {
                    "id": canonical_id, "label": draft["label"], "type": draft.get("type", "artifact"),
                    "visibility": "standard", "properties": {**draft.get("properties", {}),
                        "candidate_id": candidate["id"], "admission_id": admission_id},
                    "sources": [row["pack_id"]],
                }
            existing_edges = {item["id"] for item in world["edges"]}
            admitted_edges = []
            for draft in candidate.get("edges", []):
                relation = str(draft.get("relation", "")).strip()
                if not relation:
                    raise ValueError("candidate edge requires a relation")
                source, target = mapping[draft["source"]], mapping[draft["target"]]
                item = {"id": edge_id(source, relation, target), "source": source,
                        "relation": relation, "target": target, "assertion": "workbench_admission",
                        "confidence": None, "visibility": "standard", "sources": [row["pack_id"]],
                        "status": "active", "properties": draft.get("properties", {})}
                if item["id"] in existing_edges:
                    raise ValueError(f"canonical relation already exists: {item['id']}")
                existing_edges.add(item["id"]); admitted_edges.append(item)
            world["edges"].extend(admitted_edges)
            next_sequence = sequence + 1
            committed_state = {**state, "imagination_world": world}
            db.execute("UPDATE canonical_state SET sequence=?,imagination_world_json=?,updated_at=? WHERE singleton=1",
                       (next_sequence, json.dumps(world), now))

            for draft_id, markdown in candidate.get("lore", {}).items():
                entity_id = mapping[draft_id]
                title = world["nodes"][entity_id]["label"]
                self._append_imagination_lore(db, entity_id, title, markdown,
                                              "admission", admission_id, now, complete_markdown=True)

            pressure_records = []
            for dependency in candidate.get("genealogy", {}).get("world_dependencies", []):
                draft_subject = dependency.get("subject_draft_id")
                if draft_subject not in mapping:
                    raise ValueError("world dependency references an unknown draft entity")
                pressure_records.append({
                    "id": f"pressure:{uuid.uuid4().hex[:16]}",
                    "subject_entity_id": mapping[draft_subject], "kind": dependency["kind"],
                    "reason": dependency["reason"], "hint": dependency.get("hint"),
                    "possible_resolutions": dependency.get("possible_resolutions", ["retain_unresolved"]),
                    "source_primitive_id": dependency.get("source_primitive"),
                })
            receipt = {
                "id": admission_id, "decision": "ADMIT", "blueprint_id": blueprint_id,
                "blueprint_revision": expected_revision, "candidate_id": candidate["id"],
                "candidate_hash": candidate_hash,
                "checks": ["revision_match", "candidate_hash_match", "draft_namespace",
                           "entity_collision_free", "edge_integrity", "atomic_persistence"],
                "entity_mapping": mapping, "state_sequence_before": sequence,
                "state_sequence_after": next_sequence, "genealogy": candidate.get("genealogy", {}),
                "world_pressure_ids": [item["id"] for item in pressure_records],
            }
            db.execute("INSERT INTO imagination_admissions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (admission_id, blueprint_id, expected_revision, candidate["id"], candidate_hash,
                        sequence, next_sequence, json.dumps(mapping),
                        json.dumps(candidate.get("genealogy", {})), json.dumps(receipt), now))
            for pressure in pressure_records:
                db.execute(
                    "INSERT INTO imagination_world_pressures VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (pressure["id"], pressure["subject_entity_id"], pressure["kind"], "open",
                     pressure["reason"], json.dumps(pressure["hint"]),
                     json.dumps(pressure["possible_resolutions"]), admission_id,
                     pressure["source_primitive_id"], None, now, now),
                )

            next_revision = expected_revision + 1
            snapshot = {key: value for key, value in blueprint.items() if key != "revisions"}
            snapshot.update({"status": "admitted", "revision": next_revision,
                             "updated_at": now, "admission": receipt})
            encoded = json.dumps(snapshot)
            db.execute("UPDATE imagination_blueprints SET status='admitted',revision=?,snapshot_json=?,updated_at=? WHERE id=?",
                       (next_revision, encoded, now, blueprint_id))
            db.execute("INSERT INTO imagination_blueprint_revisions VALUES (?,?,?,?,?,?,?)",
                       (_id("blueprint_rev"), blueprint_id, next_revision, "user",
                        "admitted candidate into canonical World", encoded, now))
        assert committed_state is not None
        self.write_projections(next_sequence, committed_state)
        return self.imagination_admission(admission_id)

    def imagination_admission(self, admission_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM imagination_admissions WHERE id=?", (admission_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        for key in ("entity_mapping_json", "genealogy_json", "receipt_json"):
            item[key.removesuffix("_json")] = json.loads(item.pop(key))
        return item

    @staticmethod
    def _decode_world_pressure(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["hint"] = json.loads(item.pop("hint_json"))
        item["possible_resolutions"] = json.loads(item.pop("possible_resolutions_json"))
        return item

    def world_pressures(self, status: str | None = None) -> list[dict]:
        query = "SELECT * FROM imagination_world_pressures"
        params: tuple = ()
        if status:
            query += " WHERE status=?"; params = (status,)
        query += " ORDER BY created_at DESC"
        with self.connect() as db:
            rows = db.execute(query, params).fetchall()
        return [self._decode_world_pressure(row) for row in rows]

    def world_pressure(self, pressure_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM imagination_world_pressures WHERE id=?", (pressure_id,)).fetchone()
        return self._decode_world_pressure(row) if row else None

    def explore_world_pressure(self, pressure_id: str, title: str, artifact_type: str,
                               pack_id: str, pack_version: int, lens_id: str | None) -> dict:
        now = time.time()
        blueprint_id = f"blueprint:{uuid.uuid4().hex[:16]}"
        with self.transaction(immediate=True) as db:
            pressure = db.execute("SELECT * FROM imagination_world_pressures WHERE id=?", (pressure_id,)).fetchone()
            if not pressure:
                raise KeyError(pressure_id)
            if pressure["status"] not in {"open", "exploring"}:
                raise ValueError("resolved pressure cannot open a Workbench blueprint")
            if pressure["exploration_blueprint_id"]:
                existing = pressure["exploration_blueprint_id"]
                row = db.execute("SELECT * FROM imagination_blueprints WHERE id=?", (existing,)).fetchone()
                return self._decode_blueprint(row) if row else None
            content = {"ingredients": [], "tensions": [], "rejected_suggestions": [],
                       "open_questions": [pressure["reason"]], "draft_entities": [], "draft_edges": [],
                       "id": blueprint_id, "title": title, "artifact_type": artifact_type,
                       "status": "draft", "pack_id": pack_id, "pack_version": pack_version,
                       "lens_id": lens_id, "initiating_pressure_id": pressure_id,
                       "revision": 1, "created_at": now, "updated_at": now}
            encoded = json.dumps(content)
            db.execute("INSERT INTO imagination_blueprints VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (blueprint_id, title, artifact_type, "draft", pack_id, pack_version,
                        lens_id, pressure_id, 1, encoded, now, now))
            db.execute("INSERT INTO imagination_blueprint_revisions VALUES (?,?,?,?,?,?,?)",
                       (_id("blueprint_rev"), blueprint_id, 1, "user",
                        "opened from unresolved World pressure", encoded, now))
            db.execute("UPDATE imagination_world_pressures SET status='exploring',exploration_blueprint_id=?,updated_at=? WHERE id=?",
                       (blueprint_id, now, pressure_id))
        return self.blueprint(blueprint_id)

    def active_context(self) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM active_context WHERE singleton=1").fetchone()
        return {"global": True, "world": row["world_scope"], "task": row["task_scope"],
                "skills": json.loads(row["skill_scopes_json"]),
                "roles": json.loads(row["role_scopes_json"])}

    def set_active_context(self, world: str | None, task: str | None, skills: list[str],
                           roles: list[str] | None = None) -> dict:
        clean = sorted({s for s in skills if s.startswith("skill:")})
        with self.transaction(immediate=True) as db:
            db.execute("UPDATE active_context SET world_scope=?,task_scope=?,skill_scopes_json=?,role_scopes_json=?,updated_at=? WHERE singleton=1",
                       (world, task, json.dumps(clean), json.dumps(sorted(set(roles or []))), time.time()))
            self._bump_domain(db, "context")
        return self.active_context()

    def effective_affect(self, at: float | None = None) -> dict:
        at = at or time.time()
        values, baselines, directions = {}, {}, {}
        with self.connect() as db:
            rows = db.execute("SELECT * FROM affect_state ORDER BY rowid").fetchall()
            history = db.execute("SELECT * FROM affect_history ORDER BY created_at DESC LIMIT 24").fetchall()
        for row in rows:
            current, baseline = row["current_value"], row["baseline"]
            hours = max(0.0, (at - row["updated_at"]) / 3600.0)
            pull = min(1.0, row["homeostasis_rate"] * hours)
            effective = current + (baseline - current) * pull
            values[row["dimension"]] = round(effective, 2)
            baselines[row["dimension"]] = baseline
            directions[row["dimension"]] = "steady" if abs(effective - baseline) < .01 else "settling"
        return {"values": values, "baselines": baselines, "directions": directions,
                "history": [{**dict(r), "before": json.loads(r["before_json"]), "delta": json.loads(r["delta_json"]),
                             "after": json.loads(r["after_json"])} for r in history]}

    def preview_affect(self, values: dict[str, float], at: float | None = None) -> dict:
        """Validate an uncommitted complete Affect vector against the effective snapshot."""
        at = at or time.time()
        with self.connect() as db:
            rows = db.execute("SELECT * FROM affect_state ORDER BY rowid").fetchall()
        known = {row["dimension"]: row for row in rows}
        if set(values) != set(known):
            raise ValueError("affect proposal must contain all configured dimensions")
        before, after, delta = {}, {}, {}
        for dimension, row in known.items():
            hours = max(0.0, (at - row["updated_at"]) / 3600.0)
            current = row["current_value"] + (row["baseline"] - row["current_value"]) * min(1.0, row["homeostasis_rate"] * hours)
            value = float(values[dimension])
            change = value - current
            if not (value == value and abs(value) != float("inf")):
                raise ValueError(f"invalid affect transition for {dimension}")
            if not (1.0 <= value <= 100.0) or abs(change) > row["max_delta"]:
                raise ValueError(f"invalid affect transition for {dimension}")
            before[dimension], after[dimension], delta[dimension] = round(current, 2), round(value, 2), round(change, 2)
        return {"before": before, "after": after, "delta": delta, "committed": False}

    def memory_entries(self, channels: list[str] | None = None) -> list[dict]:
        context = self.active_context()
        scopes = ["global"] + context["skills"] + [s for s in (context["world"], context["task"]) if s]
        marks = ",".join("?" for _ in scopes)
        params: list[Any] = scopes
        where = f"(scope_type='global' OR (scope_type || ':' || scope_id) IN ({marks})) AND visibility='standard'"
        if channels:
            where += " AND channel IN (" + ",".join("?" for _ in channels) + ")"
            params.extend(channels)
        with self.connect() as db:
            rows = db.execute(f"SELECT * FROM memory_entries WHERE {where} ORDER BY created_at DESC LIMIT 300", params).fetchall()
        return [self._decode_memory_row(row) for row in rows]

    @staticmethod
    def _decode_memory_row(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["scope"] = "global" if item["scope_type"] == "global" else f"{item['scope_type']}:{item['scope_id']}"
        item["derived_from"] = json.loads(item.pop("derived_from_json"))
        for key in ("affect_before", "affect_after", "affect_delta"):
            raw = item.pop(f"{key}_json")
            item[key] = json.loads(raw) if raw else None
        return item

    def add_memory_entry(self, *, scope: str, channel: str, content: str, origin: str = "experience",
                         source_event_id: str | None = None, derived_from: list[str] | None = None,
                         affect_before: dict | None = None, affect_after: dict | None = None,
                         affect_delta: dict | None = None) -> dict:
        scope_type, _, scope_id = scope.partition(":")
        if scope_type not in {"global","skill","world","task"} or (scope_type != "global" and not scope_id):
            raise ValueError("invalid memory scope")
        if channel not in {"experience","cognitive_semantic","emotional_semantic"}:
            raise ValueError("invalid memory channel")
        entry_id, now = _id("mem"), time.time()
        with self.transaction(immediate=True) as db:
            db.execute("INSERT INTO memory_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (entry_id, scope_type, scope_id or None, channel, content, origin, source_event_id,
                        json.dumps(derived_from or []), json.dumps(affect_before) if affect_before else None,
                        json.dumps(affect_after) if affect_after else None, json.dumps(affect_delta) if affect_delta else None,
                        "standard", now))
            self._bump_domain(db, "memory")
        with self.connect() as db:
            row = db.execute("SELECT * FROM memory_entries WHERE id=?", (entry_id,)).fetchone()
        return self._decode_memory_row(row)

    def apply_affect(self, source_event_id: str, deltas: dict[str, float]) -> dict:
        now = time.time()
        with self.transaction(immediate=True) as db:
            if db.execute("SELECT 1 FROM affect_history WHERE source_event_id=?", (source_event_id,)).fetchone():
                raise ValueError("affect event already applied")
            rows = db.execute("SELECT * FROM affect_state ORDER BY rowid").fetchall()
            known = {row["dimension"]: row for row in rows}
            if not deltas or any(key not in known for key in deltas):
                raise ValueError("unknown or empty affect dimensions")
            before, after, applied = {}, {}, {}
            for dimension, row in known.items():
                hours = max(0.0, (now - row["updated_at"]) / 3600.0)
                base_value = row["current_value"] + (row["baseline"] - row["current_value"]) * min(1.0, row["homeostasis_rate"] * hours)
                delta = float(deltas.get(dimension, 0.0))
                if not (-row["max_delta"] <= delta <= row["max_delta"]):
                    raise ValueError(f"{dimension} delta exceeds configured limit")
                value = max(1.0, min(100.0, base_value + delta))
                before[dimension], after[dimension], applied[dimension] = round(base_value, 2), round(value, 2), round(value - base_value, 2)
                db.execute("UPDATE affect_state SET current_value=?,updated_at=? WHERE dimension=?", (value, now, dimension))
            history_id = _id("aff")
            db.execute("INSERT INTO affect_history VALUES (?,?,?,?,?,?,?)",
                       (history_id, source_event_id, "event", json.dumps(before), json.dumps(applied), json.dumps(after), now))
            self._bump_domain(db, "affect")
        return {"id": history_id, "source_event_id": source_event_id, "before": before, "delta": applied, "after": after, "created_at": now}

    @staticmethod
    def _bump_domain(db: sqlite3.Connection, domain: str) -> int:
        now = time.time()
        db.execute("UPDATE domain_versions SET version=version+1,updated_at=? WHERE domain=?", (now, domain))
        return db.execute("SELECT version FROM domain_versions WHERE domain=?", (domain,)).fetchone()["version"]

    def versions(self) -> dict[str, int]:
        with self.connect() as db:
            rows = db.execute("SELECT domain,version FROM domain_versions").fetchall()
        versions = {row["domain"]: row["version"] for row in rows}
        sequence, _ = self.state()
        versions["memory"] = max(versions.get("memory", 0), sequence)
        return versions

    def self_claims(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM self_claims WHERE status='active' ORDER BY kind,created_at").fetchall()
        return [dict(row) for row in rows]

    def add_self_claim(self, kind: str, subject: str, predicate: str, value: str,
                       source: str = "operator") -> dict:
        if kind not in {"identity","value","preference","commitment","relationship","goal","self_understanding"}:
            raise ValueError("invalid Self claim kind")
        if not all(part.strip() for part in (subject, predicate, value)):
            raise ValueError("Self claim fields cannot be empty")
        claim_id, now = _id("self"), time.time()
        with self.transaction(immediate=True) as db:
            version = self._bump_domain(db, "self")
            db.execute("INSERT INTO self_claims VALUES (?,?,?,?,?,'active',?,?,?)",
                       (claim_id, kind, subject.strip(), predicate.strip(), value.strip(), source, now, version))
            row = db.execute("SELECT * FROM self_claims WHERE id=?", (claim_id,)).fetchone()
        return dict(row)

    def capabilities(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM capabilities ORDER BY source,id").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for key in ("schema", "scope", "limits"):
                item[key] = json.loads(item.pop(f"{key}_json"))
            item["available"] = bool(item["available"])
            result.append(item)
        return result

    def capability(self, tool_id: str) -> dict | None:
        return next((item for item in self.capabilities() if item["id"] == tool_id), None)

    def register_mcp_capability(self, tool_id: str, server: str, description: str,
                                schema: dict, effect_class: str) -> dict:
        if not tool_id.strip() or not server.strip():
            raise ValueError("MCP tool and server are required")
        if effect_class not in {"observe","modify","communicate","execute"}:
            raise ValueError("invalid effect class")
        capability_id = f"mcp.{server.strip()}.{tool_id.strip()}"
        now = time.time()
        with self.transaction(immediate=True) as db:
            db.execute("INSERT INTO capabilities VALUES (?,?,?,?,?,'{}','{}',0,'capability-v1',?) "
                       "ON CONFLICT(id) DO UPDATE SET description=excluded.description,schema_json=excluded.schema_json,effect_class=excluded.effect_class",
                       (capability_id, f"mcp:{server.strip()}", effect_class, description.strip(), json.dumps(schema), now))
            self._bump_domain(db, "capabilities")
        return self.capability(capability_id)

    def tool_receipts(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM tool_receipts ORDER BY created_at DESC LIMIT 200").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for key in ("raw_args", "normalized_args", "context", "checks", "result"):
                raw = item.pop(f"{key}_json")
                item[key] = json.loads(raw) if raw else None
            result.append(item)
        return result

    def record_tool_receipt(self, *, tool_id: str, source: str, effect_class: str,
                            raw_args: dict, normalized_args: dict | None, context: dict,
                            decision: str, checks: list, execution_status: str,
                            result: Any = None, error: str | None = None) -> dict:
        receipt_id, now = _id("tool"), time.time()
        version = self.versions().get("capabilities", 0)
        with self.transaction(immediate=True) as db:
            db.execute("INSERT INTO tool_receipts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (receipt_id, tool_id, source, effect_class, json.dumps(raw_args),
                        json.dumps(normalized_args) if normalized_args is not None else None,
                        json.dumps(context), version, decision, json.dumps(checks), execution_status,
                        json.dumps(result) if result is not None else None, error, now, now))
            row = db.execute("SELECT * FROM tool_receipts WHERE id=?", (receipt_id,)).fetchone()
        item = dict(row)
        return item


class ConversationBusy(Exception):
    def __init__(self, turn_id: str):
        self.turn_id = turn_id


class StateConflict(Exception):
    def __init__(self, sequence: int):
        self.sequence = sequence


class BlueprintConflict(Exception):
    def __init__(self, revision: int):
        self.revision = revision


def receipt_outcome(receipt: dict) -> str:
    if receipt["decision"] == "NOOP":
        return "none"
    if receipt["decision"] == "DENY":
        return "denied"
    checks = receipt["decision_basis"]
    if any(c[1] == "ERROR" for c in checks):
        return "execution_failed"
    result = receipt.get("result") or {}
    if "noop" in result:
        return "noop"
    return "committed"


def decision_dimensions(receipt: dict, changed: bool) -> tuple[str, str, str, str]:
    checks = receipt["decision_basis"]
    terminal = checks[-1][0] if checks else "schema"
    if receipt["decision"] == "NOOP":
        return "none", "not_run", "not_required", terminal
    if receipt["decision"] == "DENY":
        return "denied", "not_run", "not_required", terminal
    if any(c[1] == "ERROR" for c in checks):
        return "admitted", "failed", "not_required", terminal
    execution = "applied" if changed else "noop"
    return "admitted", execution, "committed" if changed else "not_required", terminal
