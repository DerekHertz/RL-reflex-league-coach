from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
import typer

from lolcoach.analysis.build import build_fact_sheet
from lolcoach.config import get_settings
from lolcoach.detectors.context import AnalysisContext
from lolcoach.detectors.registry import DETECTORS
from lolcoach.detectors.runner import run_detectors
from lolcoach.domain.match import MatchView, PeerComparison
from lolcoach.domain.timeline import TimelineIndex
from lolcoach.llm.narrator import narrate_match
from lolcoach.metrics.economy import cs_per_minute, gold_diff_at, gold_per_minute
from lolcoach.riot.cache import FileRawCache
from lolcoach.riot.client import RiotClient
from lolcoach.riot.rate_limiter import HeaderAwareLimiter

app = typer.Typer(add_completion=False)


@asynccontextmanager
async def make_riot_client() -> AsyncIterator[RiotClient]:
    settings = get_settings()
    cache = FileRawCache(settings.cache_dir)
    limiter = HeaderAwareLimiter()
    async with httpx.AsyncClient(timeout=30.0) as http:
        yield RiotClient(api_key=settings.riot_api_key, limiter=limiter, cache=cache, http=http)


@app.command()
def fetch(
    riot_id: str = typer.Argument(..., help="gameName#tagLine, e.g. 'Player#NA1'"),
    count: int = typer.Option(20, help="Number of recent matches to fetch"),
    queue: int | None = typer.Option(None, help="Queue id filter, e.g. 420 for ranked solo/duo"),
) -> None:
    """Resolve a Riot ID and populate the local cache with their recent matches + timelines."""

    async def run() -> None:
        start = time.monotonic()
        async with make_riot_client() as client:
            typer.echo(f"Resolving {riot_id}...")
            player = await client.resolve_player(riot_id)
            typer.echo(f"puuid={player.puuid} platform={player.platform.value} cluster={player.cluster.value}")

            match_ids = await client.match_ids(player.puuid, player.cluster, count=count, queue=queue)
            typer.echo(f"Found {len(match_ids)} matches. Fetching match + timeline for each...")

            for i, match_id in enumerate(match_ids, start=1):
                await client.match_and_timeline(match_id)
                typer.echo(f"  [{i}/{len(match_ids)}] {match_id}")

        elapsed = time.monotonic() - start
        typer.echo(
            f"Done in {elapsed:.1f}s. requests={client.request_count} throttled_429s={client.throttled_count}"
        )

    asyncio.run(run())


def _load_cached(match_id: str) -> tuple[MatchView, TimelineIndex]:
    settings = get_settings()
    cache = FileRawCache(settings.cache_dir)
    match_raw = cache.get("match", match_id)
    timeline_raw = cache.get("timeline", match_id)
    if match_raw is None or timeline_raw is None:
        raise typer.BadParameter(
            f"{match_id} not found in cache ({settings.cache_dir}). Run `lolcoach fetch` first."
        )
    return MatchView(match_raw), TimelineIndex(timeline_raw)


def _comparison_dict(c: PeerComparison) -> dict[str, float | int | None]:
    return {
        "value": c.metric_value,
        "peer_value": c.peer_value,
        "delta": c.delta,
        "rank_in_lobby": c.rank_in_lobby,
    }


@app.command()
def analyze(
    match_id: str = typer.Argument(..., help="Match ID, e.g. NA1_4567890123"),
    puuid: str = typer.Option(..., help="PUUID of the subject to analyze"),
    as_json: bool = typer.Option(False, "--json", help="Print machine-readable JSON instead of a summary"),
    detectors: bool = typer.Option(False, "--detectors", help="Also run and print detector results"),
) -> None:
    """Print peer-relative metrics for one participant in an already-cached match.

    No network access -- run `lolcoach fetch` first to populate the cache.
    """
    match, timeline = _load_cached(match_id)
    subject = match.participant_by_puuid(puuid)
    peers = match.peer_group(subject)

    if detectors:
        ctx = AnalysisContext(match=match, timeline=timeline, subject=subject, peers=peers)
        for result in run_detectors(ctx, DETECTORS):
            typer.echo(f"[{result.outcome.value}] {result.detector_id} ({result.duration_ms:.1f}ms)")
            if result.reason:
                typer.echo(f"    reason: {result.reason}")
            for finding in result.findings:
                evidence_str = ", ".join(f"{e.key}={e.value}" for e in finding.evidence)
                typer.echo(f"    finding {finding.id} [{finding.severity.name}] {evidence_str}")
        typer.echo("")

    duration_min = match.duration_s / 60.0
    gold_diffs = {
        minute: gold_diff_at(timeline, subject.participant_id, peers.lane_opponent.participant_id, minute)
        for minute in (10, 15, 20)
        if peers.lane_opponent is not None and minute <= duration_min
    }

    gpm_cmp = peers.compare(
        lambda p: gold_per_minute(p, match.duration_s), higher_is_better=True, peer="role_cohort"
    )
    csm_cmp = peers.compare(
        lambda p: cs_per_minute(p, match.duration_s), higher_is_better=True, peer="lane_opponent"
    )

    result = {
        "match_id": match.match_id,
        "subject_champion": subject.champion_name,
        "team_position": subject.team_position,
        "duration_min": round(duration_min, 1),
        "win": subject.win,
        "lane_opponent_champion": peers.lane_opponent.champion_name if peers.lane_opponent else None,
        "gold_diff_vs_lane_opponent": gold_diffs,
        "gold_per_minute": _comparison_dict(gpm_cmp),
        "cs_per_minute": _comparison_dict(csm_cmp),
    }

    if as_json:
        typer.echo(json.dumps(result, indent=2))
        return

    typer.echo(f"{match.match_id} -- {subject.champion_name} ({subject.team_position or 'unknown'})")
    typer.echo(f"  duration: {duration_min:.1f} min, result: {'WIN' if subject.win else 'LOSS'}")
    if peers.lane_opponent is not None:
        typer.echo(f"  lane opponent: {peers.lane_opponent.champion_name}")
        for minute, diff in gold_diffs.items():
            sign = "+" if (diff or 0) >= 0 else ""
            typer.echo(f"    gold diff @{minute}min: {sign}{diff}")
    else:
        typer.echo("  lane opponent: none (teamPosition unavailable -- ARAM or role-swap game)")
    typer.echo(
        f"  GPM: {gpm_cmp.metric_value:.0f} "
        f"(role cohort avg {gpm_cmp.peer_value:.0f}, rank {gpm_cmp.rank_in_lobby}/10 in lobby)"
        if gpm_cmp.metric_value is not None and gpm_cmp.peer_value is not None
        else "  GPM: n/a"
    )
    typer.echo(
        f"  CS/min: {csm_cmp.metric_value:.1f} "
        f"(lane opponent {csm_cmp.peer_value:.1f}, rank {csm_cmp.rank_in_lobby}/10 in lobby)"
        if csm_cmp.metric_value is not None and csm_cmp.peer_value is not None
        else f"  CS/min: {csm_cmp.metric_value:.1f}" if csm_cmp.metric_value is not None else "  CS/min: n/a"
    )


@app.command()
def narrate(
    match_id: str = typer.Argument(..., help="Match ID, e.g. NA1_4567890123"),
    puuid: str = typer.Option(..., help="PUUID of the subject to analyze"),
    show_factsheet: bool = typer.Option(False, "--show-factsheet", help="Print the fact sheet JSON sent to Claude"),
) -> None:
    """Run detectors, build the fact sheet, and print Claude's coaching narrative.

    No network access to Riot -- run `lolcoach fetch` first. Requires ANTHROPIC_API_KEY.
    """
    match, timeline = _load_cached(match_id)
    ctx = AnalysisContext.build(match, timeline, puuid)
    results = run_detectors(ctx, DETECTORS)
    sheet = build_fact_sheet(ctx, results)

    if show_factsheet:
        typer.echo(sheet.model_dump_json(indent=2))
        typer.echo("")

    async def run() -> None:
        response, used_fallback = await narrate_match(sheet)
        if used_fallback:
            typer.echo("[guard] Claude's narration failed validation twice -- showing the deterministic fallback.\n")

        typer.echo(f"=== {sheet.subject.champion} ({sheet.subject.role}) -- {sheet.match.result.upper()} {sheet.match.duration} ===\n")
        typer.echo(response.headline)
        typer.echo("")
        if response.what_went_well:
            typer.echo("What went well:")
            for item in response.what_went_well:
                typer.echo(f"  - {item}")
            typer.echo("")
        if response.narrations:
            typer.echo("Focus areas:")
            for n in response.narrations:
                typer.echo(f"  [{n.finding_id}]")
                typer.echo(f"    {n.explanation}")
                typer.echo(f"    Fix: {n.fix}")
                if n.drill:
                    typer.echo(f"    Drill: {n.drill}")
            typer.echo("")
        typer.echo(response.closing)

    asyncio.run(run())


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8420, help="Bind port"),
    reload: bool = typer.Option(False, help="Auto-reload on code changes (development only)"),
) -> None:
    """Run the FastAPI web server."""
    import uvicorn

    uvicorn.run("lolcoach.api.app:app", host=host, port=port, reload=reload)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
