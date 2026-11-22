"""Démonstration Streamlit avec le même parcours que l’interface de l’API."""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from api.runtime import Runtime
from reco_platform.service import Recommender, RequestError

STATIC = Path(__file__).with_name("static")
LOGGER = logging.getLogger(__name__)

st.set_page_config(page_title="Prisme — Découvre ce qui te plaît", page_icon="🔶", layout="wide")
st.html("""
<style>
[data-testid="stAppViewContainer"], [data-testid="stMain"] {background:#151311;}
[data-testid="stMainBlockContainer"] {padding:0;max-width:none;}
[data-testid="stHeader"], [data-testid="stDecoration"], [data-testid="stToolbar"] {display:none;}
[data-testid="stVerticalBlock"] {gap:0;}
</style>
""")


def data_uri(name, content_type="image/webp"):
    encoded = base64.b64encode((STATIC / name).read_bytes()).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


@st.cache_resource(show_spinner="Chargement du catalogue Prisme…")
def resources():
    runtime = Runtime(Recommender.load(external_catalogs=os.getenv("RECO_EXTERNAL_CATALOGS", "1") == "1"))
    assets = {
        "hero": data_uri("hero.webp"),
        "tiles": [data_uri(f"art-{index}.webp") for index in range(12)],
    }
    css = (STATIC / "prisme.css").read_text(encoding="utf-8")
    for path in STATIC.glob("*.woff2"):
        css = css.replace(f"/assets/{path.name}", data_uri(path.name, "font/woff2"))
    js = (STATIC / "app.js").read_text(encoding="utf-8").replace("export function mount", "function mount")
    bridge = (STATIC / "streamlit-bridge.js").read_text(encoding="utf-8")
    component = st.components.v2.component(
        "prisme", html=(STATIC / "shell.html").read_text(encoding="utf-8"), css=css, js=js + "\n" + bridge,
    )
    return runtime, assets, component


runtime, assets, component = resources()


def on_command():
    command = st.session_state.prisme.command
    if not isinstance(command, dict) or type(command.get("id")) is not int:
        return
    response = {"id": command["id"]}
    try:
        if len(str(command)) > 16384 or not runtime.limits.allowed(st.session_state.prisme_session):
            raise RequestError("Limite de requêtes atteinte. Réessaie dans une minute.", 429)
        response["value"] = runtime.operation(command.get("action"), command.get("payload"))
    except RequestError as error:
        response["error"] = str(error)
    except ValidationError:
        response["error"] = "La sélection ou le domaine est invalide."
    except Exception:
        LOGGER.exception("Action Streamlit indisponible")
        response["error"] = "Le serveur n’a pas pu traiter cette demande."
    st.session_state.prisme_response = response


if "prisme_session" not in st.session_state:
    from uuid import uuid4

    st.session_state.prisme_session = uuid4().hex
component(
    key="prisme",
    data={"metadata": runtime.engine.metadata(), "assets": assets,
          "response": st.session_state.get("prisme_response")},
    on_command_change=on_command,
)
