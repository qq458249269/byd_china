"""Vehicle model."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, model_validator

from ..models._base import BydBaseModel, BydTimestamp


class EmpowerRange(BydBaseModel):
    """A permission scope granted to a shared user."""

    # BYD sometimes sends "childList" instead of "children".
    _KEY_ALIASES: ClassVar[dict[str, str]] = {
        "childList": "children",
    }

    code: str = ""
    name: str = ""
    children: list[EmpowerRange] = Field(default_factory=list)


class Vehicle(BydBaseModel):
    """A vehicle associated with the user's account."""

    vin: str = ""
    model_name: str = ""
    brand_name: str = ""
    energy_type: str = ""
    auto_alias: str = ""
    auto_plate: str = ""
    pic_main_url: str = ""
    pic_set_url: str = ""
    out_model_type: str = ""
    total_mileage: float | None = None
    model_id: int | None = None
    car_type: int | None = None
    default_car: bool = False
    empower_type: int | None = None
    permission_status: int | None = None
    tbox_version: str = ""
    vehicle_state: str = ""
    channel: int | None = None
    auto_bought_time: BydTimestamp = None
    yun_active_time: BydTimestamp = None
    empower_id: str | None = None
    range_detail_list: list[EmpowerRange] = Field(default_factory=list)

    @property
    def is_shared(self) -> bool:
        if self.empower_id is not None and str(self.empower_id).strip() != "":
            return True
        return False

    @model_validator(mode="after")
    def _fill_missing_pics(self) -> Vehicle:
        if self.pic_main_url and self.pic_set_url:
            return self
        raw = self.raw if isinstance(self.raw, dict) else {}
        nested = raw.get("cfPic")
        if not isinstance(nested, dict):
            return self
        pic_main = self.pic_main_url or str(nested.get("picMainUrl") or nested.get("pic_main_url") or "")
        pic_set = self.pic_set_url or str(nested.get("picSetUrl") or nested.get("pic_set_url") or "")
        return self.model_copy(update={"pic_main_url": pic_main, "pic_set_url": pic_set})
