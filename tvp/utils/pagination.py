import math
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

from tvp.errors import BadRequestError


class PaginationParams(BaseModel):
    page: int = Field(examples=[1], gt=0)
    page_size: int = Field(examples=[20], gt=0, lt=101)


PaginationParamsQuery = Annotated[PaginationParams, Query()]


class PaginationMetadata(BaseModel):
    total_pages: int = Field(examples=[57], gt=0)
    total_items: int = Field(examples=[1024], gt=-1)
    page_size: int = Field(examples=[20], gt=0, lt=101)
    current_page: int = Field(examples=[1], gt=0)


class PaginatedAPIResponse[T](BaseModel):
    items: list[T]
    metadata: PaginationMetadata


def generate_paginated_response[T](
    items: list[T], total_items: int, pagination_params: PaginationParams
) -> PaginatedAPIResponse[T]:
    # Generate metadata
    # Ensure total_items is non-negative
    total_items = max(total_items, 0)

    # 1. Calculate total pages
    if total_items == 0:
        total_pages = 1
    else:
        # Use math.ceil to ensure correct rounding up for the last partial page
        total_pages = math.ceil(total_items / pagination_params.page_size)
        total_pages = int(total_pages)  # Ensure it's an integer

    # Ensure current_page does not exceed total_pages
    if pagination_params.page > total_pages:
        msg = "Invalid page number."
        raise BadRequestError(msg)

    metadata = PaginationMetadata(
        total_pages=total_pages,
        total_items=total_items,
        page_size=pagination_params.page_size,
        current_page=pagination_params.page,
    )

    return PaginatedAPIResponse[T](items=items, metadata=metadata)
