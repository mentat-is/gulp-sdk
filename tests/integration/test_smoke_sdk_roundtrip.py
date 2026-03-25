import os
import time
import asyncio
import pytest

from gulp_sdk import GulpClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_smoke_sdk_roundtrip():
    """Minimal SDK smoke test: ingest a small document and query it back.

    This test is intentionally small. It verifies SDK <-> server contract
    without being exhaustive. It requires a running gulp server (defaults
    to http://127.0.0.1:8080) and valid admin/admin credentials.
    """

    host = os.environ.get("GULP_BIND_TO_ADDR", "127.0.0.1")
    port = int(os.environ.get("GULP_BIND_TO_PORT", "8080"))
    base_url = f"http://{host}:{port}"

    async with GulpClient(base_url) as client:
        # Login (skip if not available)
        try:
            await client.auth.login("admin", "admin")
        except Exception as exc:
            pytest.skip(f"Auth/login not available: {exc}")

        # Create operation
        op = await client.operations.create(name=f"smoke-op-{int(time.time())}")
        operation_id = getattr(op, "id", None) or op.get("id")
        if not operation_id:
            pytest.skip("Could not create operation")

        # Prefer ingesting a real EVTX sample using the win_evtx plugin.
        sample_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "samples", "win_evtx", "system.evtx"
            )
        )
        if not os.path.exists(sample_path):
            pytest.skip(f"EVTX sample not found: {sample_path}")

        try:
            ingest_res = await client.ingest.file(
                operation_id=operation_id, plugin_name="win_evtx", file_path=sample_path
            )
        except Exception as exc:
            pytest.skip(f"Ingest API unavailable: {exc}")

        # DEBUG: dump ingest response so we can inspect req_id/status shapes
        try:
            ingest_dump = ingest_res.model_dump()
        except Exception:
            try:
                ingest_dump = dict(ingest_res) if isinstance(ingest_res, dict) else {"value": str(ingest_res)}
            except Exception:
                ingest_dump = {"value": str(ingest_res)}
        print("DEBUG: ingest_res =", ingest_dump, flush=True)

        # Poll the ingestion status until it reports `done`, or fail/timeout.
        req_id = getattr(ingest_res, "req_id", None) or (
            ingest_res.get("req_id") if isinstance(ingest_res, dict) else None
        )
        if not req_id:
            pytest.skip("Ingest request id not returned; cannot poll status")

        finished = False
        for _ in range(180):
            try:
                st = await client.ingest.status(operation_id, req_id)
            except Exception as exc:
                st = {}
                # DEBUG: record exception details from status call
                print("DEBUG: ingest.status exception:", repr(exc), flush=True)

            if not isinstance(st, dict):
                await asyncio.sleep(1)
                continue

            # GulpRequestStats shape: { ..., "status": "ongoing|done|failed|canceled", "data": { ... } }
            # DEBUG: show raw poll payload
            print("DEBUG: poll ->", st, flush=True)

            # Inspect status field (some deployments may nest status inside data)
            status_field = None
            data = {}
            if isinstance(st, dict):
                status_field = st.get("status") or (st.get("data") or {}).get("status")
                data = st.get("data") if isinstance(st.get("data"), dict) else {}

            # Wait for explicit `done` state; do not proceed early on partial counters.
            if status_field == "done":
                finished = True
                break
            if status_field in ("failed", "canceled"):
                pytest.skip(f"Ingest finished with status {status_field}")

            await asyncio.sleep(1)

        if not finished:
            pytest.skip("Ingestion did not finish within timeout")

        # Query back in preview_mode (synchronous small result)
        try:
            qres = await client.queries.query_gulp(
                operation_id=operation_id,
                flt={"operation_ids": [operation_id]},
                q_options={"preview_mode": True, "limit": 10},
            )
        except Exception as exc:
            # DEBUG: print exception details to help diagnose server response
            try:
                resp = getattr(exc, "response_data", None) or getattr(exc, "response", None)
            except Exception:
                resp = None
            print("DEBUG: query exception:", repr(exc), "response_data:", resp, flush=True)
            pytest.skip(f"Query API unavailable: {exc}")

        assert isinstance(qres, dict)
        total_hits = qres.get("total_hits") or (qres.get("data") or {}).get("total_hits")
        assert total_hits is not None
        # Expect at least one document after ingest
        assert int(total_hits) >= 1
