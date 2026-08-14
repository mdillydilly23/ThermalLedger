"""Plume model route — Gaussian plume attribution, internal only."""

from fastapi import APIRouter
from pydantic import BaseModel
from datetime import date

router = APIRouter()


class PlumeAttributionRequest(BaseModel):
    facility_id: str
    start: date
    end: date


@router.post("/attribute")
async def attribute_plume(req: PlumeAttributionRequest):
    """
    Run Gaussian plume dispersion model to attribute satellite CH4 to facility.
    Input: facility coordinates + ERA5 wind fields from data/raw/era5/
    Output: per-facility CH4 estimate with 95% confidence interval.
    """
    # TODO: implement xarray raster load + scipy Gaussian plume model
    raise NotImplementedError
