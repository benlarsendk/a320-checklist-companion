"""SimBrief API client for fetching flight plans."""

import logging
from typing import Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SIMBRIEF_API_URL = "https://www.simbrief.com/api/xml.fetcher.php"


class FlightPlan(BaseModel):
    """Parsed flight plan data from SimBrief OFP."""

    # Route info
    origin: str = ""
    destination: str = ""
    alternate: str = ""
    route: str = ""
    flight_number: str = ""

    # Fuel (in units specified)
    fuel_block: int = 0  # Block/ramp fuel
    fuel_takeoff: int = 0
    fuel_landing: int = 0
    fuel_units: str = "KGS"  # KGS or LBS

    # Weights
    payload: int = 0
    zfw: int = 0  # Zero fuel weight
    tow: int = 0  # Takeoff weight
    ldw: int = 0  # Landing weight
    weight_units: str = "KGS"

    # Performance
    cruise_altitude: str = ""
    cost_index: int = 0

    # Weather (for baro setting)
    origin_metar: str = ""
    dest_metar: str = ""
    origin_qnh: int = 0  # In hPa
    dest_qnh: int = 0

    # Trim
    trim_percent: float = 0.0

    def format_fuel(self, value: int) -> str:
        """Format fuel value with units."""
        return f"{value:,} {self.fuel_units}"

    def format_weight(self, value: int) -> str:
        """Format weight value with units."""
        return f"{value:,} {self.weight_units}"


class SimBriefError(Exception):
    """Base exception for SimBrief API errors."""

    pass


class SimBriefUserNotFound(SimBriefError):
    """Username not found or no flight plan available."""

    pass


class SimBriefNetworkError(SimBriefError):
    """Network error when connecting to SimBrief."""

    pass


class SimBriefClient:
    """Async client for SimBrief API."""

    def __init__(self):
        self._flight_plan: Optional[FlightPlan] = None

    @property
    def flight_plan(self) -> Optional[FlightPlan]:
        """Get the cached flight plan."""
        return self._flight_plan

    def clear_flight_plan(self):
        """Clear the cached flight plan."""
        self._flight_plan = None

    async def fetch_flight_plan(self, username: str) -> FlightPlan:
        """
        Fetch the latest flight plan from SimBrief.

        Args:
            username: SimBrief username or pilot ID

        Returns:
            FlightPlan with parsed OFP data

        Raises:
            SimBriefUserNotFound: Username not found or no flight plan
            SimBriefNetworkError: Network error
            SimBriefError: Other API errors
        """
        if not username:
            raise SimBriefError("Username is required")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    SIMBRIEF_API_URL,
                    params={"username": username, "json": "1"},
                )
                response.raise_for_status()
                data = response.json()

        except httpx.TimeoutException:
            raise SimBriefNetworkError("Request timed out")
        except httpx.NetworkError as e:
            raise SimBriefNetworkError(f"Network error: {e}")
        except httpx.HTTPStatusError as e:
            raise SimBriefNetworkError(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            raise SimBriefError(f"Failed to fetch flight plan: {e}")

        # Check for API errors
        if "fetch" in data and "status" in data["fetch"]:
            status = data["fetch"]["status"]
            if status == "Error":
                msg = data["fetch"].get("message", "Unknown error")
                if "User not found" in msg or "No flight plan" in msg:
                    raise SimBriefUserNotFound(msg)
                raise SimBriefError(msg)

        # Parse the OFP data
        try:
            flight_plan = self._parse_ofp(data)
            self._flight_plan = flight_plan
            logger.info(
                f"Flight plan fetched: {flight_plan.origin} -> {flight_plan.destination}"
            )
            return flight_plan
        except Exception as e:
            logger.error(f"Failed to parse OFP: {e}")
            raise SimBriefError(f"Failed to parse flight plan: {e}")

    def _parse_ofp(self, data: dict) -> FlightPlan:
        """Parse SimBrief OFP JSON into FlightPlan model."""
        # Extract sections
        origin = data.get("origin", {})
        destination = data.get("destination", {})
        alternate = data.get("alternate", {})
        general = data.get("general", {})
        fuel = data.get("fuel", {})
        weights = data.get("weights", {})
        params = data.get("params", {})

        # Determine units
        units = params.get("units", "kgs").upper()
        if units == "KGS":
            fuel_units = "KG"
            weight_units = "KG"
        else:
            fuel_units = "LBS"
            weight_units = "LBS"

        # Extract QNH from origin/destination weather if available
        origin_qnh = 0
        dest_qnh = 0
        origin_wx = data.get("weather", {}).get("orig_metar", "")
        dest_wx = data.get("weather", {}).get("dest_metar", "")

        # Parse QNH from METAR (Q1013 or A2992 format)
        origin_qnh = self._parse_qnh(origin_wx)
        dest_qnh = self._parse_qnh(dest_wx)

        # Extract trim if available
        trim_percent = 0.0
        try:
            trim_percent = float(general.get("stepclimb_string", "0").split("/")[0] or 0)
        except (ValueError, IndexError):
            pass

        # Try to get trim from weights section
        if weights.get("est_trim"):
            try:
                trim_percent = float(weights.get("est_trim", 0))
            except ValueError:
                pass

        return FlightPlan(
            # Route
            origin=origin.get("icao_code", ""),
            destination=destination.get("icao_code", ""),
            alternate=alternate.get("icao_code", "") if alternate else "",
            route=general.get("route", ""),
            flight_number=general.get("flight_number", ""),
            # Fuel
            fuel_block=int(fuel.get("plan_ramp", 0)),
            fuel_takeoff=int(fuel.get("plan_takeoff", 0)),
            fuel_landing=int(fuel.get("plan_landing", 0)),
            fuel_units=fuel_units,
            # Weights
            payload=int(weights.get("payload", 0)),
            zfw=int(weights.get("est_zfw", 0)),
            tow=int(weights.get("est_tow", 0)),
            ldw=int(weights.get("est_ldw", 0)),
            weight_units=weight_units,
            # Performance
            cruise_altitude=general.get("initial_altitude", ""),
            cost_index=int(general.get("costindex", 0)),
            # Weather
            origin_metar=origin_wx,
            dest_metar=dest_wx,
            origin_qnh=origin_qnh,
            dest_qnh=dest_qnh,
            # Trim
            trim_percent=trim_percent,
        )

    def _parse_qnh(self, metar: str) -> int:
        """Parse QNH from METAR string. Returns hPa."""
        if not metar:
            return 0

        # Look for Q#### (hPa) or A#### (inHg)
        import re

        # QNH in hPa (e.g., Q1013)
        match = re.search(r"Q(\d{4})", metar)
        if match:
            return int(match.group(1))

        # QNH in inHg (e.g., A2992) - convert to hPa
        match = re.search(r"A(\d{4})", metar)
        if match:
            inhg = int(match.group(1)) / 100.0
            return int(inhg * 33.8639)

        return 0


# Global client instance
simbrief_client = SimBriefClient()
