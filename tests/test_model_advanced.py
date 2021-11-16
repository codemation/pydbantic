import time
import pytest
from pydbantic import Database
from tests.models import Journey, Coordinate

@pytest.mark.asyncio
async def test_database(db_url):
    await Database.create(
        db_url,
        tables=[Journey],
        cache_enabled=False,
        testing=True
    )

    journey = await Journey.create(
        waypoints=[Coordinate(latitude=1.0, longitude=1.0), Coordinate(latitude=1.0, longitude=1.0)]
    )

    all_coordinates = await Coordinate.all()

    assert len(all_coordinates) == 2
    

    all_journeys = await Journey.all()
    assert len(all_journeys) ==1
    assert len(all_journeys[0].waypoints) == 2

    for coordinate in all_coordinates:
        await coordinate.delete()

    all_journeys = await Journey.all()
    assert len(all_journeys[0].waypoints) == 0

    all_journeys[0].waypoints=all_coordinates
    await all_journeys[0].save()

    all_journeys = await Journey.all()
    assert len(all_journeys[0].waypoints) == 2

    all_journeys[0].waypoints.pop(0)
    await all_journeys[0].save()

    all_journeys = await Journey.all()
    assert len(all_journeys[0].waypoints) == 1

    journey = await Journey.create(
        waypoints=all_journeys[0].waypoints
    )

    all_journeys = await Journey.all()
    assert len(all_journeys) == 2
    assert all_journeys[0].waypoints == all_journeys[1].waypoints

    await all_journeys[1].waypoints[0].delete()

    all_journeys = await Journey.all()
    assert all_journeys[0].waypoints == all_journeys[1].waypoints