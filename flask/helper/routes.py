"""
Flask routes for the RFAOII demo site
-------------------------------------
Responsible only for parsing / encoding and running the algorithms.
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    url_for,
)


sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")),
)

import fairpyx.algorithms.repeated_Fair_Allocation_of_Indivisible_Items as rfaoi  

bp = Blueprint("main", __name__)
log = logging.getLogger("fairpyx.web")
logging.basicConfig(level=logging.INFO)

# ────────────────────────── helpers ──────────────────────────────────────────
def _coerce_utils(raw: str) -> dict[int, dict[int, float]]:
    """
    Accept either JSON or a Python-dict literal and coerce **all keys to int**.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:

        data = eval(raw, {})  
    out: dict[int, dict[int, float]] = {}
    for a_lbl, items in data.items():
        a = int(a_lbl)
        out[a] = {int(it): float(val) for it, val in items.items()}
    if set(out) != {0, 1}:
        abort(
            400,
            "The current demo supports *exactly* two agents, labelled 0 and 1.",
        )
    return out


def _run_with_log_capture(func, *args, **kw) -> tuple[Any, str]:
    """
    Run *func* while capturing stdout, stderr **and** logging output.
    Returns a tuple  (func-result, captured-text).
    """
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        root = logging.getLogger()
        prev_level = root.level
        tmp_handler = logging.StreamHandler(buf)
        tmp_handler.setFormatter(
            logging.Formatter("%(levelname).1s %(name)s: %(message)s")
        )
        root.setLevel(logging.DEBUG)
        root.addHandler(tmp_handler)
        try:
            result = func(*args, **kw)
        finally:
            root.removeHandler(tmp_handler)
            root.setLevel(prev_level)
    return result, buf.getvalue()


def _round_values(rounds, utils):
    """
    Build per-round valuation data in the form expected by the table template.

    Returned structure
    ------------------
    vals[idx][agent]["own" | "other"]  (0 ≤ idx < #rounds, agent ∈ {0,1})
    """
    vals: list[dict[int, dict[str, float]]] = []
    for rd in rounds:
        a0_own   = sum(utils[0][o] for o in rd[0])
        a0_other = sum(utils[0][o] for o in rd[1])
        a1_own   = sum(utils[1][o] for o in rd[1])
        a1_other = sum(utils[1][o] for o in rd[0])
        vals.append(
            {
                0: {"own": a0_own, "other": a0_other},
                1: {"own": a1_own, "other": a1_other},
            }
        )
    return vals


# ───────────────────────────── routes ───────────────────────────────────────
@bp.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        utils_raw = request.form["utilities"]
        k = int(request.form.get("k", 2))
        algo_sel = request.form.get("algo", "1")
        utils = _coerce_utils(utils_raw)

        if algo_sel == "1":
            if k != 2:
                abort(400, "Algorithm 1 works only for k = 2.")
            rounds, log_txt = _run_with_log_capture(rfaoi.algorithm1, utils)
            checks = [
                [rfaoi.EF1_holds(rd, a, utils) for a in (0, 1)]
                for rd in rounds
            ]
            vals = _round_values(rounds, utils)
            return render_template(
                "algo1.html",
                utils=utils,
                rounds=rounds,
                checks=checks,
                vals=vals,
                k=k,
                log_txt=log_txt,
            )

        # ⇒ Algorithm 2
        if k % 2:
            abort(400, "Algorithm 2 requires an *even* k.")
        rounds, log_txt = _run_with_log_capture(rfaoi.algorithm2, k, utils)
        checks = [
            [rfaoi.weak_EF1_holds(rd, a, utils) for a in (0, 1)]
            for rd in rounds
        ]
        vals = _round_values(rounds, utils)
        return render_template(
            "algo2.html",
            utils=utils,
            rounds=rounds,
            checks=checks,
            vals=vals,
            k=k,
            log_txt=log_txt,
        )

    # GET – empty form
    return render_template("index.html")


@bp.route("/about")
def about():
    return render_template("about.html")
