"""Test that Govee adapters populate stable_id on DeviceInfo."""

from unittest.mock import MagicMock

import pytest
from govee_fakes import LAMP, lamp_record

from dj_ledfx.devices.govee.adapter_base import GoveeAdapterBase
from dj_ledfx.devices.govee.colour import GoveeColourAdapter
from dj_ledfx.devices.govee.razer import GoveeRazerAdapter


@pytest.mark.parametrize("kind", [GoveeRazerAdapter, GoveeColourAdapter])
def test_a_lamp_is_known_by_its_device_id(kind: type[GoveeAdapterBase]) -> None:
    adapter = kind(MagicMock(), lamp_record(), 10)
    assert adapter.device_info.stable_id == LAMP == "govee:test-lamp"
