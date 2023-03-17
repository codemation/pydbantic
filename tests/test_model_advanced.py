import pytest

from pydbantic import Database
from tests.models import Coordinate, Journey


@pytest.mark.asyncio
async def test_database(db_url):
    await Database.create(
        db_url, tables=[Journey, Coordinate], cache_enabled=False, testing=True
    )

    journey = await Journey.create(waypoints=[])

    await Coordinate.create(lat_long=(1.0, 1.0), journeys=[journey])

    await Coordinate.create(lat_long=(1.0, 1.1), journeys=[journey])

    all_coordinates = await Coordinate.all()
    # breakpoint()

    assert len(all_coordinates) == 2

    all_journeys = await Journey.all()
    assert len(all_journeys) == 1

    assert len(all_journeys[0].waypoints) == 2

    for coordinate in all_coordinates:
        await coordinate.delete()

    all_journeys = await Journey.all()

    assert len(all_journeys[0].waypoints) == 0

    for coordinate in all_coordinates:
        coordinate.journeys = []

    all_journeys[0].waypoints = all_coordinates
    await all_journeys[0].save()

    all_journeys = await Journey.all()
    assert len(all_journeys[0].waypoints) == 2

    waypoint_to_delete = all_journeys[0].waypoints.pop(0)
    await waypoint_to_delete.delete()

    all_journeys = await Journey.all()
    assert len(all_journeys[0].waypoints) == 1

    journey = await Journey.create(waypoints=all_journeys[0].waypoints)

    all_journeys = await Journey.all()
    assert len(all_journeys) == 2
    assert (
        all_journeys[0].waypoints[0].lat_long == all_journeys[1].waypoints[0].lat_long
    )

    await all_journeys[1].waypoints[0].delete()

    all_journeys = await Journey.all()
    assert all_journeys[0].waypoints == all_journeys[1].waypoints

    assert len(all_journeys[0].waypoints) == 0

    all_journeys[0].waypoints = all_coordinates
    await all_journeys[0].save()

    all_journeys = await Journey.all()
    assert len(all_journeys[0].waypoints) == 2
