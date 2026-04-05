import math

import httpx
import pytest
import respx
from inventra_collector.application.collect_page_and_publish import (
    collect_page_and_publish,
)
from inventra_collector.domain import Item, Itens
from inventra_collector.infrastructure.config import Config


@pytest.mark.asyncio
@respx.mock(assert_all_mocked=True)
async def test_collect_page_html_and_publish_to_items_with_valid_page_should_return_items(
    mocker,
):

    mocker.patch.object(
        Config.SefazApi, "url", "https://www.example.com/example-endpoint"
    )

    publisher = mocker.AsyncMock()

    with open("inventra-collector/mock-pages/page-mock.html", "r") as file:
        page_html = file.read()

    respx.get(
        "https://www.example.com/example-endpoint?p=00000000000000000000000000000000000000000000"
    ).mock(return_value=httpx.Response(200, content=page_html))

    result = await collect_page_and_publish(
        key_access="00000000000000000000000000000000000000000000"
    )

    publisher.publish.assert_called_once()

    published_data = publisher.publish.call_args.args[0]
    assert result is True
    assert isinstance(published_data, Itens)
    assert len(published_data.itens) == 7
    assert (
        Item(
            description="ling tipo calab perdigao kg",
            value_unit=47.48,
            quantity=1,
            value_total=47.48,
            unit="kg",
            key_access="00000000000000000000000000000000000000000000",
            hash="000000000000000000000000000000000000000000002023-09-01T12:00:00",
        )
        in published_data.itens
    )
    assert math.isclose(
        sum([item.value_total for item in published_data.itens]), 99.97, rel_tol=1e-2
    )


@pytest.mark.asyncio
@respx.mock(assert_all_mocked=True)
async def test_collect_page_html_and_publish_to_items_with_invalid_page_should_return_empty_items(
    mocker,
):

    mocker.patch.object(
        Config.SefazApi, "url", "https://www.example.com/example-endpoint"
    )

    publisher = mocker.AsyncMock()

    with open("inventra-collector/mock-pages/page-mock-invalid.html", "r") as file:
        page_html = file.read()

    respx.get("https://www.example.com/example-endpoint?p=0000000000000000000").mock(
        return_value=httpx.Response(200, content=page_html)
    )

    result = await collect_page_and_publish(key_access="0000000000000000000")

    publisher.publish.assert_not_called()
    assert result is False
