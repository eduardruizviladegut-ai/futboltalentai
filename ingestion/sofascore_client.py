"""
Cliente de la API interna de Sofascore.

IMPORTANTE — naturaleza de esta integración:
  Sofascore no ofrece una API pública ni licencia de uso comercial.
  Este cliente accede a los mismos endpoints JSON que usa su propia
  web (sofascore.com/api/v1/...). Es una decisión consciente para la
  v1 del proyecto (ver conversación de diseño); antes de monetizar
  hay que migrar a una fuente con licencia (Sportmonks, API-Football...).

Por qué curl_cffi y no `requests`:
  Sofascore está detrás de Cloudflare y bloquea clientes HTTP que no
  imitan el fingerprint TLS/JA3 de un navegador real. curl_cffi permite
  "impersonar" Chrome sin necesidad de levantar un navegador headless
  completo (más ligero que Selenium, más barato de correr en Render).

  Si en el futuro Cloudflare bloquea también esta vía, el fallback es
  Selenium + undetected-chromedriver (más pesado, requiere Chrome
  instalado en el entorno de ejecución).
"""

import time
import random
from curl_cffi import requests as curl_requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

BASE_URL = "https://www.sofascore.com/api/v1"

# Cabeceras completas imitando un navegador real. El impersonate="chrome124"
# ya iguala el fingerprint TLS/HTTP2, pero Cloudflare también evalúa el
# conjunto de cabeceras HTTP -- un Referer/Accept-Language ausente es
# una señal de bot fácil de detectar.
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}


class SofascoreRateLimitError(Exception):
    pass


class SofascoreClient:
    def __init__(self, min_delay: float = 2.5, max_delay: float = 5.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.session = curl_requests.Session(impersonate="chrome124", headers=DEFAULT_HEADERS)

    def _sleep(self):
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(SofascoreRateLimitError),
    )
    def _get(self, path: str) -> dict:
        url = f"{BASE_URL}/{path.lstrip('/')}"
        response = self.session.get(url, timeout=20)

        if response.status_code == 429:
            raise SofascoreRateLimitError(f"Rate limited en {path}")
        response.raise_for_status()

        self._sleep()
        return response.json()

    def warm_up(self) -> None:
        """
        Visita la home de Sofascore primero, para que la sesión reciba
        las cookies (ej. cf_clearance) que Cloudflare exige antes de
        aceptar peticiones a /api/v1/... Reduce (no elimina) el riesgo
        de 403 en la primera petición a la API.
        """
        try:
            self.session.get("https://www.sofascore.com/", timeout=20)
            self._sleep()
        except Exception:
            pass  # si falla el warm-up, seguimos igual con los reintentos normales

    # ------------------------------------------------------------------
    # Endpoints usados por la ingesta v1
    # ------------------------------------------------------------------

    def get_tournament_seasons(self, tournament_id: int) -> dict:
        """Temporadas disponibles para una competición (unique-tournament)."""
        return self._get(f"unique-tournament/{tournament_id}/seasons")

    def get_league_player_statistics(
        self,
        tournament_id: int,
        season_id: int,
        fields: list[str],
        offset: int = 0,
        limit: int = 100,
        accumulation: str = "total",
    ) -> dict:
        """
        Stats agregadas de todos los jugadores de una liga/temporada.
        Este es el endpoint principal para nutrir player_stats_snapshot.
        """
        fields_param = "%2C".join(fields)
        path = (
            f"unique-tournament/{tournament_id}/season/{season_id}/statistics"
            f"?limit={limit}&order=-rating&offset={offset}"
            f"&accumulation={accumulation}&fields={fields_param}"
        )
        return self._get(path)

    def get_team(self, team_id: int) -> dict:
        return self._get(f"team/{team_id}")
