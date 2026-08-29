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


class SofascoreRateLimitError(Exception):
    pass


class SofascoreClient:
    def __init__(self, min_delay: float = 1.5, max_delay: float = 3.5):
        self.min_delay = min_delay
        self.max_delay = max_delay

    def _sleep(self):
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(SofascoreRateLimitError),
    )
    def _get(self, path: str) -> dict:
        url = f"{BASE_URL}/{path.lstrip('/')}"
        response = curl_requests.get(url, impersonate="chrome124", timeout=20)

        if response.status_code == 429:
            raise SofascoreRateLimitError(f"Rate limited en {path}")
        response.raise_for_status()

        self._sleep()
        return response.json()

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
